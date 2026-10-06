import asyncio
from datetime import datetime, timezone
import logging
import os
from dotenv import load_dotenv
from typing import List, Dict, Any, Tuple, Set, Optional

from .models import Candle
from .db import Database
from .scorer import IndicatorScorer
from .classifier import MarketClassifier
from .mt5_adapter import adapter, TIMEFRAME_NAME_TO_INT

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MT5Sync")

TIMEFRAME_MAP = TIMEFRAME_NAME_TO_INT

# Callback registry to notify API/websockets when new state classifications are generated
# This acts as our Pub/Sub channel for live streaming
websocket_broadcast_callback = None

class MT5SyncWorker:
    def __init__(self, db: Database, scorer: IndicatorScorer, classifier: MarketClassifier):
        self.db = db
        self.scorer = scorer
        self.classifier = classifier
        self.is_running = False
        
        # Monitor targets loaded from database persistence
        db_targets = self.db.get_monitored_markets()
        if db_targets:
            self.targets: Set[Tuple[str, str]] = {(t["symbol"], t["timeframe"]) for t in db_targets}
        else:
            self.targets: Set[Tuple[str, str]] = {("XAUUSD", "M15")}
        
        # State caches keyed by (symbol, timeframe_str)
        self.previous_signals_map: Dict[Tuple[str, str], Dict[str, Any]] = {}
        self.last_processed_times: Dict[Tuple[str, str], datetime] = {}
        
        # Load credentials if configured in .env
        self.login_id = os.getenv("MT5_LOGIN")
        self.password = os.getenv("MT5_PASSWORD")
        self.server = os.getenv("MT5_SERVER")

    @property
    def is_synthetic(self) -> bool:
        return adapter.is_synthetic

    def add_target(self, symbol: str, timeframe: str) -> bool:
        if timeframe not in TIMEFRAME_MAP:
            logger.error(f"Unsupported timeframe: {timeframe}")
            return False
        # Normalize symbol name (e.g. upper case)
        symbol = symbol.upper()
        self.targets.add((symbol, timeframe))
        self.db.add_monitored_market(symbol, timeframe)
        logger.info(f"Added monitoring target: {symbol} on {timeframe}")
        return True

    def remove_target(self, symbol: str, timeframe: str):
        symbol = symbol.upper()
        self.targets.discard((symbol, timeframe))
        self.db.remove_monitored_market(symbol, timeframe)
        logger.info(f"Removed monitoring target: {symbol} on {timeframe}")

    def get_targets(self) -> List[Dict[str, str]]:
        return [{"symbol": t[0], "timeframe": t[1]} for t in self.targets]

    async def sync_single_target(self, symbol: str, tf_str: str):
        if tf_str not in TIMEFRAME_MAP:
            return
        tf_const = TIMEFRAME_MAP[tf_str]
        symbol = symbol.upper()
        
        # Initialize MT5/adapter if needed
        init_success = False
        if self.login_id and self.password and self.server:
            init_success = adapter.initialize(
                login=int(self.login_id),
                password=self.password,
                server=self.server
            )
        else:
            init_success = adapter.initialize()

        if not init_success:
            logger.error(f"MT5/Adapter initialization failed in sync_single_target: {adapter.last_error()}")
            return
            
        if not adapter.symbol_select(symbol, True):
            logger.error(f"Failed to select symbol {symbol} in MT5 terminal.")
            return

        rates = adapter.copy_rates_from_pos(symbol, tf_const, 0, 1000)
        if rates is None or len(rates) == 0:
            logger.error(f"Failed to copy rates for {symbol} on {tf_str}. Error: {adapter.last_error()}")
            return

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

        history = self.db.get_candles(symbol=symbol, timeframe=tf_str, limit=1000)
        if len(history) >= 2:
            latest_time = history[-1].time
            classification_res = self.classifier.classify(history)
            self.db.save_classification(latest_time, classification_res.classification, symbol=symbol, timeframe=tf_str)
            self.last_processed_times[(symbol, tf_str)] = latest_time
            logger.info(f"On-demand sync complete for {symbol} ({tf_str}). Ingested {len(history)} bars.")

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

        self.sync_task = asyncio.create_task(self.sync_loop())

    async def stop(self):
        self.is_running = False
        adapter.shutdown()
        logger.info("MT5/Adapter integration shut down.")

    async def sync_loop(self):
        while self.is_running:
            try:
                # 1. Initialize MT5/Adapter
                init_success = False
                if self.login_id and self.password and self.server:
                    init_success = adapter.initialize(
                        login=int(self.login_id),
                        password=self.password,
                        server=self.server
                    )
                else:
                    init_success = adapter.initialize()

                if not init_success:
                    logger.error(f"MT5 initialization failed, error code: {adapter.last_error()}. Retrying in 10s...")
                    await asyncio.sleep(10)
                    continue

                # 2. Loop over all target symbols and timeframes
                active_targets = list(self.targets)
                for symbol, tf_str in active_targets:
                    tf_const = TIMEFRAME_MAP[tf_str]
                    
                    # Ensure symbol is active
                    if not adapter.symbol_select(symbol, True):
                        logger.error(f"Failed to select/activate symbol {symbol} in MT5 terminal.")
                        continue
                        
                    # Fetch rates (copy latest 1000 bars)
                    rates = adapter.copy_rates_from_pos(symbol, tf_const, 0, 1000)
                    if rates is None or len(rates) == 0:
                        logger.error(f"Failed to copy rates for {symbol} on {tf_str}. Error: {adapter.last_error()}")
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
                        
                        # 5. Evaluate and resolve pending predictions against latest price action
                        pending = self.db.get_pending_predictions(symbol, tf_str)
                        latest_candle = history[-1]
                        for p in pending:
                            p_id = p["id"]
                            tp = p["take_profit"]
                            sl = p["stop_loss"]
                            rec = p["recommendation"]
                            regime = p["primary_regime"]
                            sigs = p["indicator_signals"]
                            
                            resolved_status = None
                            if "BUY" in rec and tp and sl:
                                if latest_candle.high >= tp:
                                    resolved_status = "SUCCESS_TP"
                                elif latest_candle.low <= sl:
                                    resolved_status = "FAIL_SL"
                            elif "SELL" in rec and tp and sl:
                                if latest_candle.low <= tp:
                                    resolved_status = "SUCCESS_TP"
                                elif latest_candle.high >= sl:
                                    resolved_status = "FAIL_SL"
                                    
                            if resolved_status:
                                self.db.resolve_prediction(p_id, resolved_status, latest_candle.close)
                                is_win = (resolved_status == "SUCCESS_TP")
                                for ind_name, sig_info in sigs.items():
                                    sig = sig_info.get("signal")
                                    ind_correct = (is_win and (("BUY" in rec and sig == "BUY") or ("SELL" in rec and sig == "SELL")))
                                    self.db.update_indicator_score(ind_name, regime, ind_correct)
                                logger.info(f"Resolved Prediction #{p_id} for {symbol} ({tf_str}): {resolved_status}. Dynamic Reliability scores updated in SQLite!")

                        # Save new prediction log on new candle close if signal active
                        if last_processed and latest_time > last_processed:
                            if classification_res.trade_setup or classification_res.confidence_buy > 60 or classification_res.confidence_sell > 60:
                                entry = history[-1].close
                                sl = classification_res.trade_setup.stop_loss if classification_res.trade_setup else None
                                tp = classification_res.trade_setup.take_profit if classification_res.trade_setup else None
                                sigs_dict = {k: {"signal": v.signal, "confidence": v.confidence} for k, v in classification_res.indicator_signals.items()}
                                self.db.save_prediction(
                                    symbol=symbol,
                                    timeframe=tf_str,
                                    primary_regime=classification_res.classification.primary_regime,
                                    recommendation=classification_res.recommendation,
                                    buy_conf=classification_res.confidence_buy,
                                    sell_conf=classification_res.confidence_sell,
                                    entry_price=entry,
                                    stop_loss=sl,
                                    take_profit=tp,
                                    indicator_signals=sigs_dict
                                )

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
