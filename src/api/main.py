from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any
import os

from contextlib import asynccontextmanager
from src.engine.models import Candle, MarketStateResponse
from src.engine.db import Database
from src.engine.scorer import IndicatorScorer
from src.engine.classifier import MarketClassifier
from src.engine.mt5_sync import MT5SyncWorker

# Initialize Database and components
db = Database()
scorer = IndicatorScorer(db)
classifier = MarketClassifier(db)
sync_worker = MT5SyncWorker(db, scorer, classifier)

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

# Keep a cache of the previous signals to calculate scores upon next candle arrival
previous_signals: Dict[str, Any] = {}

@app.post("/api/candles", response_model=MarketStateResponse)
async def ingest_candle(candle: Candle):
    global previous_signals
    try:
        # 1. Save new candle to db
        db.save_candle(candle)
        
        # 2. Retrieve history (need history to calculate indicators)
        history = db.get_candles(limit=1000)
        
        if len(history) < 2:
            # Not enough data to run scoring
            classification_res = classifier.classify(history)
            previous_signals = {k: v.model_copy() for k, v in classification_res.indicator_signals.items()}
            return classification_res
            
        # 3. If we have previous signals cache, evaluate them with the new candle
        regime = "Mean Reversion"
        # Pre-classify to get current regime
        classification_res = classifier.classify(history)
        regime = classification_res.classification.primary_regime
        
        if previous_signals:
            scorer.evaluate_and_update(history, previous_signals, regime)
            
        # 4. Run classification with updated database weights
        classification_res = classifier.classify(history)
        
        # 5. Save classification to DB
        db.save_classification(candle.time, classification_res.classification)
        
        # 6. Cache current signals for next time
        previous_signals = {k: v.model_copy() for k, v in classification_res.indicator_signals.items()}
        
        return classification_res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/state", response_model=MarketStateResponse)
async def get_current_state():
    history = db.get_candles(limit=1000)
    if not history:
        raise HTTPException(status_code=404, detail="No market data ingested yet.")
    res = classifier.classify(history)
    return res

@app.get("/api/scores")
async def get_indicator_scores():
    return db.get_indicator_scores()

# Mount Static Web Interface
web_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web")
if os.path.exists(web_dir):
    app.mount("/", StaticFiles(directory=web_dir, html=True), name="web")
