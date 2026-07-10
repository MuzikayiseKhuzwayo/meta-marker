import MetaTrader5 as mt5
import asyncio
from datetime import datetime, timezone
import logging
import os
from dotenv import load_dotenv
from typing import List, Dict, Any

from .models import Candle
from .db import Database
from .scorer import IndicatorScorer
from .classifier import MarketClassifier

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MT5Sync")

class MT5SyncWorker:
    def __init__(self, db: Database, scorer: IndicatorScorer, classifier: MarketClassifier, symbol: str = "XAUUSD"):
        self.db = db
        self.scorer = scorer
        self.classifier = classifier
        self.symbol = symbol
        self.timeframe = mt5.TIMEFRAME_M15
        self.is_running = False
        self.previous_signals: Dict[str, Any] = {}
        
        # Load credentials if configured in .env
        self.login_id = os.getenv("MT5_LOGIN")
        self.password = os.getenv("MT5_PASSWORD")
        self.server = os.getenv("MT5_SERVER")
        self.last_processed_candle_time = None

    async def start(self):
        self.is_running = True
        logger.info("Starting MT5 Direct Integration Sync worker...")
        
        # Connect to database and load existing cache if any
        history = self.db.get_candles(limit=2)
        if len(history) >= 1:
            # Seed previous signals with the current classification
            try:
                state = self.classifier.classify(self.db.get_candles(limit=1000))
                self.previous_signals = {k: v.model_copy() for k, v in state.indicator_signals.items()}
            except Exception:
                pass

        asyncio.create_task(self.sync_loop())

    async def stop(self):
        self.is_running = False
        mt5.shutdown()
        logger.info("MT5 direct integration shut down.")

    async def sync_loop(self):
        while self.is_running:
            try:
                # 1. Initialize MT5 (with explicit login if configured, otherwise default parameters)
                init_success = False
                if self.login_id and self.password and self.server:
                    logger.info(f"Attempting MT5 initialization with credentials for login {self.login_id}...")
                    init_success = mt5.initialize(
                        login=int(self.login_id),
                        password=self.password,
                        server=self.server
                    )
                else:
                    logger.info("Attempting parameterless MT5 initialization...")
                    init_success = mt5.initialize()

                if not init_success:
                    logger.error(f"MT5 initialization failed, error code: {mt5.last_error()}. Retrying in 10s...")
                    await asyncio.sleep(10)
                    continue

                # 2. Fetch rates
                # Copy latest 1000 bars
                rates = mt5.copy_rates_from_pos(self.symbol, self.timeframe, 0, 1000)
                if rates is None or len(rates) == 0:
                    logger.error(f"Failed to copy rates for {self.symbol}. Error: {mt5.last_error()}")
                    await asyncio.sleep(10)
                    continue

                logger.info(f"Retrieved {len(rates)} bars from MT5 for {self.symbol}")

                # 3. Synchronize candles into the database
                new_candles_count = 0
                synced_candles: List[Candle] = []

                for rate in rates:
                    # MT5 rates are numpy void types. Time is posix timestamp.
                    dt = datetime.fromtimestamp(int(rate['time']), tz=timezone.utc)
                    candle = Candle(
                        time=dt,
                        open=float(rate['open']),
                        high=float(rate['high']),
                        low=float(rate['low']),
                        close=float(rate['close']),
                        volume=float(rate['tick_volume'])
                    )
                    synced_candles.append(candle)
                    
                # Batch save
                # Save each to DB (Database.save_candle performs an INSERT OR REPLACE)
                for c in synced_candles:
                    self.db.save_candle(c)

                # 4. Process calculations and scoring
                history = self.db.get_candles(limit=1000)
                if len(history) >= 2:
                    latest_time = history[-1].time
                    
                    # Only evaluate/score if we have advanced to a new candle close
                    if self.last_processed_candle_time and latest_time > self.last_processed_candle_time:
                        # Determine regime at previous candle
                        classification_res = self.classifier.classify(history[:-1])
                        regime = classification_res.classification.primary_regime
                        
                        # Evaluate previous signals
                        if self.previous_signals:
                            self.scorer.evaluate_and_update(history, self.previous_signals, regime)
                            logger.info(f"New candle closed at {latest_time}. Evaluated previous signals.")
                            
                    # Run classifier with newly updated scores for the latest candle
                    classification_res = self.classifier.classify(history)
                    self.db.save_classification(latest_time, classification_res.classification)
                    
                    # Cache current signals for next loop iteration
                    self.previous_signals = {k: v.model_copy() for k, v in classification_res.indicator_signals.items()}
                    self.last_processed_candle_time = latest_time
                    logger.info(f"Sync calculation complete. Current Recommendation: {classification_res.recommendation}")

            except Exception as e:
                logger.error(f"Error in MT5 sync loop: {e}", exc_info=True)

            # Poll every 15 seconds (ideal for M15 candles)
            await asyncio.sleep(15)
