from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from typing import List, Dict, Any, Set, Optional
import os
import io
import csv
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from pydantic import BaseModel

from src.engine.models import Candle, MarketStateResponse
from src.engine.db import Database
from src.engine.scorer import IndicatorScorer
from src.engine.classifier import MarketClassifier
from src.engine.mt5_sync import MT5SyncWorker
from src.engine.mt5_adapter import adapter
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
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(manager.broadcast(classification.model_dump_json()))
    except Exception:
        pass

mt5_sync.websocket_broadcast_callback = ws_callback

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start MT5/Adapter Background synchronization task
    await sync_worker.start()
    yield
    # Shutdown MT5/Adapter connection
    await sync_worker.stop()

app = FastAPI(
    title="Meta-Marker Market Intelligence Engine",
    description="Deterministic Market Classification, Dynamic Reliability Scoring, and Live MT5/Synthetic Bridge",
    version="1.0.0",
    lifespan=lifespan
)

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
@app.get("/api/health")
async def get_health():
    """
    Health check and active bridge telemetry.
    """
    targets = sync_worker.get_targets()
    return {
        "status": "healthy",
        "mode": "SYNTHETIC_SIMULATION" if sync_worker.is_synthetic else "LIVE_MT5",
        "is_synthetic": sync_worker.is_synthetic,
        "active_targets": targets,
        "database": db.db_path,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@app.get("/api/diagnostics")
async def get_diagnostics():
    """
    Detailed hardware, memory, and database telemetry.
    """
    proc_data = {}
    try:
        import psutil
        proc = psutil.Process()
        mem_info = proc.memory_info()
        proc_data = {
            "memory_rss_mb": round(mem_info.rss / 1024 / 1024, 2),
            "cpu_percent": proc.cpu_percent()
        }
    except Exception:
        proc_data = {"memory_rss_mb": 0.0, "cpu_percent": 0.0}

    targets = sync_worker.get_targets()
    scores = db.get_indicator_scores()
    recent_preds = db.get_recent_predictions(limit=10)
    
    return {
        "engine_mode": "SYNTHETIC_SIMULATION" if sync_worker.is_synthetic else "LIVE_MT5",
        "process": proc_data,
        "monitored_targets_count": len(targets),
        "indicators_scored_count": len(scores),
        "recent_predictions_count": len(recent_preds),
        "last_adapter_error": adapter.last_error()
    }

@app.get("/api/broker/symbols")
async def get_broker_symbols():
    """
    Fetch all active symbols supported by the connected broker terminal or synthetic feed.
    """
    if not adapter.initialize():
        raise HTTPException(status_code=500, detail=f"Failed to connect to MT5 terminal: {adapter.last_error()}")
    
    symbols = adapter.symbols_get()
    if symbols is None:
        raise HTTPException(status_code=500, detail="Failed to fetch symbol list from MT5/Adapter.")
    
    return [s.name for s in symbols]

@app.get("/api/state", response_model=MarketStateResponse)
async def get_current_state(symbol: str = "XAUUSD", timeframe: str = "M15"):
    symbol = symbol.upper()
    # Auto-register target in background sync worker
    sync_worker.add_target(symbol, timeframe)
    
    history = db.get_candles(symbol=symbol, timeframe=timeframe, limit=1000)
    if not history:
        # Perform on-demand single-pass sync so the first request retrieves data immediately
        await sync_worker.sync_single_target(symbol, timeframe)
        history = db.get_candles(symbol=symbol, timeframe=timeframe, limit=1000)
        
    if not history:
        raise HTTPException(status_code=404, detail=f"No market data ingested for {symbol} ({timeframe}) yet. Ensure symbol is available.")
        
    res = classifier.classify(history)
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

@app.get("/api/predictions/history")
async def get_predictions_history(symbol: Optional[str] = None, limit: int = 50):
    """
    Retrieve real-time prediction resolution audit history and win-rate resolution stats.
    """
    history = db.get_recent_predictions(symbol=symbol, limit=limit)
    total = len(history)
    resolved = [p for p in history if p["status"] in ("SUCCESS_TP", "FAIL_SL")]
    wins = [p for p in resolved if p["status"] == "SUCCESS_TP"]
    win_rate = (len(wins) / len(resolved) * 100.0) if resolved else 0.0
    return {
        "total_audited": total,
        "resolved_count": len(resolved),
        "win_rate": round(win_rate, 1),
        "predictions": history
    }

@app.get("/api/export/audit.csv")
async def export_audit_csv(symbol: Optional[str] = None, limit: int = 500):
    """
    Export verified prediction audit log as streamable CSV.
    """
    history = db.get_recent_predictions(symbol=symbol, limit=limit)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "id", "symbol", "timeframe", "timestamp", "primary_regime",
        "recommendation", "buy_confidence", "sell_confidence",
        "entry_price", "stop_loss", "take_profit", "status",
        "resolved_at", "resolved_price"
    ])
    for p in history:
        writer.writerow([
            p.get("id"), p.get("symbol"), p.get("timeframe"), p.get("timestamp"),
            p.get("primary_regime"), p.get("recommendation"), p.get("buy_confidence"),
            p.get("sell_confidence"), p.get("entry_price"), p.get("stop_loss"),
            p.get("take_profit"), p.get("status"), p.get("resolved_at"), p.get("resolved_price")
        ])
    csv_content = output.getvalue()
    filename = f"meta_marker_audit_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.get("/api/export/candles")
async def export_candles(symbol: str = "XAUUSD", timeframe: str = "M15", limit: int = 1000):
    """
    Export historical candle series as JSON.
    """
    candles = db.get_candles(symbol=symbol.upper(), timeframe=timeframe, limit=limit)
    return [c.model_dump() for c in candles]

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

# Mount Static Web Interface & Showcase
project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
showcase_dir = os.path.join(project_root, "showcase")
if os.path.exists(showcase_dir):
    app.mount("/showcase", StaticFiles(directory=showcase_dir, html=True), name="showcase")

web_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web")
if os.path.exists(web_dir):
    app.mount("/", StaticFiles(directory=web_dir, html=True), name="web")
