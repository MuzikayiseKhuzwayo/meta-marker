import MetaTrader5 as mt5
import asyncio
from datetime import datetime, timezone
import logging
import os
from dotenv import load_dotenv
from typing import List, Dict, Any, Tuple, Set

from .models import Candle
from .db import Database
from .scorer import IndicatorScorer
from .classifier import MarketClassifier

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MT5Sync")

TIMEFRAME_MAP = {
    "M1": mt5.TIMEFRAME_M1,
    "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30,
    "H1": mt5.TIMEFRAME_H1,
    "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1
}

# Callback registry to notify API/websockets when new state classifications are generated
# This acts as our Pub/Sub channel for live streaming
websocket_broadcast_callback = None

class MT5SyncWorker:
    def __init__(self, db: Database, scorer: IndicatorScorer, classifier: MarketClassifier):
        self.db = db
        self.scorer = scorer
        self.classifier = classifier
        self.is_running = False
        
        # Monitor targets: Set of (symbol, timeframe_str)
        self.targets: Set[Tuple[str, str]] = {("XAUUSD", "M15")}
        
        # State caches keyed by (symbol, timeframe_str)
        self.previous_signals_map: Dict[Tuple[str, str], Dict[str, Any]] = {}
        self.last_processed_times: Dict[Tuple[str, str], datetime] = {}
        
        # Load credentials if configured in .env
        self.login_id = os.getenv("MT5_LOGIN")
        self.password = os.getenv("MT5_PASSWORD")
        self.server = os.getenv("MT5_SERVER")

    def add_target(self, symbol: str, timeframe: str) -> bool:
        if timeframe not in TIMEFRAME_MAP:
            logger.error(f"Unsupported timeframe: {timeframe}")
            return False
        # Normalize symbol name (e.g. upper case)
        symbol = symbol.upper()
        self.targets.add((symbol, timeframe))
        logger.info(f"Added monitoring target: {symbol} on {timeframe}")
        return True

    def remove_target(self, symbol: str, timeframe: str):
        symbol = symbol.upper()
        self.targets.discard((symbol, timeframe))
        logger.info(f"Removed monitoring target: {symbol} on {timeframe}")

    def get_targets(self) -> List[Dict[str, str]]:
        return [{"symbol": t[0], "timeframe": t[1]} for t in self.targets]

    async def start(self):
        self.is_running = True
        logger.info("Starting MT5 Direct Integration Sync worker...")
        
        # Seed cache for existing targets from database
        for symbol, tf in self.targets:
            history = self.db.get_candles(symbol=symbol, timeframe=tf, limit=2)
            if len(history) >= 1:
                try:
                    state = self.classifier.classify(self.db.get_candles(symbol=symbol, timeframe=tf, limit=1000))
                    self.previous_signals_map[(symbol, tf)] = {k: v.model_copy() for k, v in state.indicator_signals.items()}
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
                    init_success = mt5.initialize(
                        login=int(self.login_id),
                        password=self.password,
                        server=self.server
                    )
                else:
                    init_success = mt5.initialize()

                if not init_success:
                    logger.error(f"MT5 initialization failed, error code: {mt5.last_error()}. Retrying in 10s...")
                    await asyncio.sleep(10)
                    continue

                # 2. Loop over all target symbols and timeframes
                # Make a copy of targets to prevent concurrent modification issues
                active_targets = list(self.targets)
                for symbol, tf_str in active_targets:
                    tf_const = TIMEFRAME_MAP[tf_str]
                    
                    # Ensure symbol is active in MT5 Market Watch
                    if not mt5.symbol_select(symbol, True):
                        logger.error(f"Failed to select/activate symbol {symbol} in MT5 terminal.")
                        continue
                        
                    # Fetch rates (copy latest 1000 bars)
                    rates = mt5.copy_rates_from_pos(symbol, tf_const, 0, 1000)
                    if rates is None or len(rates) == 0:
                        logger.error(f"Failed to copy rates for {symbol} on {tf_str}. Error: {mt5.last_error()}")
                        continue

                    # 3. Synchronize candles into database
                    synced_candles: List[Candle] = []
                    for rate in rates:
                        dt = datetime.fromtimestamp(int(rate['time']), tz=timezone.utc)
                        candle = Candle(
                            time=dt,
                            open=float(rate['open']),
                            high=float(rate['high']),
                            low=float(rate['low']),
                            close=float(rate['close']),
                            volume=float(rate['tick_volume']),
                            symbol=symbol,
                            timeframe=tf_str
                        )
                        synced_candles.append(candle)
                        
                    for c in synced_candles:
                        self.db.save_candle(c)

                    # 4. Process calculations and scoring
                    history = self.db.get_candles(symbol=symbol, timeframe=tf_str, limit=1000)
                    if len(history) >= 2:
                        latest_time = history[-1].time
                        last_processed = self.last_processed_times.get((symbol, tf_str))
                        
                        # Only evaluate/score if we have advanced to a new candle close
                        if last_processed and latest_time > last_processed:
                            classification_res = self.classifier.classify(history[:-1])
                            regime = classification_res.classification.primary_regime
                            
                            prev_sigs = self.previous_signals_map.get((symbol, tf_str))
                            if prev_sigs:
                                self.scorer.evaluate_and_update(history, prev_sigs, regime)
                                logger.info(f"New candle closed for {symbol} ({tf_str}) at {latest_time}. Evaluated previous signals.")
                                
                        # Run classifier with newly updated scores for the latest candle
                        classification_res = self.classifier.classify(history)
                        self.db.save_classification(latest_time, classification_res.classification, symbol=symbol, timeframe=tf_str)
                        
                        # Cache current signals for next loop iteration
                        self.previous_signals_map[(symbol, tf_str)] = {
                            k: v.model_copy() for k, v in classification_res.indicator_signals.items()
                        }
                        self.last_processed_times[(symbol, tf_str)] = latest_time
                        
                        # Broadcast websocket update to clients
                        if websocket_broadcast_callback:
                            websocket_broadcast_callback(classification_res)

            except Exception as e:
                logger.error(f"Error in MT5 sync loop: {e}", exc_info=True)

            # Poll every 10 seconds (responsive to multiple timeframes)
            await asyncio.sleep(10)
