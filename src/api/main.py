from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any, Set
import os
import MetaTrader5 as mt5
from contextlib import asynccontextmanager
from pydantic import BaseModel

from src.engine.models import Candle, MarketStateResponse
from src.engine.db import Database
from src.engine.scorer import IndicatorScorer
from src.engine.classifier import MarketClassifier
from src.engine.mt5_sync import MT5SyncWorker
import src.engine.mt5_sync as mt5_sync

# WebSocket Connection Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)

    async def broadcast(self, message: str):
        # Broadcast to all active clients
        for connection in list(self.active_connections):
            try:
                await connection.send_text(message)
            except Exception:
                self.disconnect(connection)

manager = ConnectionManager()

# Global database and engine components
db = Database()
scorer = IndicatorScorer(db)
classifier = MarketClassifier(db)
sync_worker = MT5SyncWorker(db, scorer, classifier)

# Attach WebSocket broadcast callback
def ws_callback(classification: MarketStateResponse):
    import asyncio
    loop = asyncio.get_event_loop()
    if loop.is_running():
        asyncio.create_task(manager.broadcast(classification.model_dump_json()))

mt5_sync.websocket_broadcast_callback = ws_callback

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start MT5 Background synchronization task
    await sync_worker.start()
    yield
    # Shutdown MT5 connection
    await sync_worker.stop()

app = FastAPI(title="Meta-Marker MIE API", lifespan=lifespan)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Models
class MonitorRequest(BaseModel):
    symbol: str
    timeframe: str

# Endpoints
@app.get("/api/broker/symbols")
async def get_broker_symbols():
    """
    Fetch all active symbols supported by the connected broker.
    """
    if not mt5.initialize():
        raise HTTPException(status_code=500, detail=f"Failed to connect to MT5 terminal: {mt5.last_error()}")
    
    symbols = mt5.symbols_get()
    if symbols is None:
        raise HTTPException(status_code=500, detail="Failed to fetch symbol list from MT5.")
    
    return [s.name for s in symbols]

@app.get("/api/state", response_model=MarketStateResponse)
async def get_current_state(symbol: str = "XAUUSD", timeframe: str = "M15"):
    symbol = symbol.upper()
    history = db.get_candles(symbol=symbol, timeframe=timeframe, limit=1000)
    if not history:
        raise HTTPException(status_code=404, detail=f"No market data ingested for {symbol} ({timeframe}) yet.")
    res = classifier.classify(history)
    # Ensure correct symbol/timeframe is explicitly stated in response
    res.symbol = symbol
    res.timeframe = timeframe
    return res

@app.get("/api/monitor/targets")
async def get_monitor_targets():
    return sync_worker.get_targets()

@app.post("/api/monitor/add")
async def add_monitor_target(req: MonitorRequest):
    success = sync_worker.add_target(req.symbol, req.timeframe)
    if not success:
        raise HTTPException(status_code=400, detail=f"Invalid monitor target or timeframe: {req.timeframe}")
    return {"status": "success", "targets": sync_worker.get_targets()}

@app.post("/api/monitor/remove")
async def remove_monitor_target(req: MonitorRequest):
    sync_worker.remove_target(req.symbol, req.timeframe)
    return {"status": "success", "targets": sync_worker.get_targets()}

@app.get("/api/scores")
async def get_indicator_scores():
    return db.get_indicator_scores()

# WebSocket Endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# Mount Static Web Interface
web_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web")
if os.path.exists(web_dir):
    app.mount("/", StaticFiles(directory=web_dir, html=True), name="web")
