"""
MetaTrader 5 Bridge Adapter with Graceful Fallback & Synthetic Simulation.
Enables Meta-Marker to run seamlessly on Windows with native MT5,
as well as headless Linux, macOS, CI/CD runners, and offline demo environments.
"""

import sys
import logging
import random
import math
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Any, Union

logger = logging.getLogger("MT5Adapter")

# Check platform and library availability
MT5_AVAILABLE = False
mt5 = None

if sys.platform == "win32":
    try:
        import MetaTrader5 as mt5_module
        mt5 = mt5_module
        MT5_AVAILABLE = True
        logger.info("MetaTrader5 C-extension library loaded successfully.")
    except ImportError as e:
        logger.warning(f"MetaTrader5 library not available: {e}. Falling back to Synthetic Simulation Mode.")
else:
    logger.info("Running on non-Windows OS. Falling back to Synthetic Simulation Mode.")

# Standard MT5 Timeframe Constants
TIMEFRAME_M1 = 1
TIMEFRAME_M5 = 5
TIMEFRAME_M15 = 15
TIMEFRAME_M30 = 30
TIMEFRAME_H1 = 16385
TIMEFRAME_H4 = 16388
TIMEFRAME_D1 = 16408

TIMEFRAME_MINUTES = {
    "M1": 1,
    "M5": 5,
    "M15": 15,
    "M30": 30,
    "H1": 60,
    "H4": 240,
    "D1": 1440
}

TIMEFRAME_NAME_TO_INT = {
    "M1": TIMEFRAME_M1,
    "M5": TIMEFRAME_M5,
    "M15": TIMEFRAME_M15,
    "M30": TIMEFRAME_M30,
    "H1": TIMEFRAME_H1,
    "H4": TIMEFRAME_H4,
    "D1": TIMEFRAME_D1
}

# Synthetic Base Prices for Standard Instruments
BASE_PRICES = {
    "XAUUSD": 2350.0,
    "EURUSD": 1.0850,
    "GBPUSD": 1.2720,
    "USDJPY": 156.40,
    "BTCUSD": 64200.0,
    "ETHUSD": 3450.0,
    "NAS100": 19800.0,
    "US30": 39500.0,
    "SPX500": 5480.0
}


class SyntheticMarketFeed:
    """
    Generates realistic geometric Brownian motion candle series with
    support/resistance levels, trend runs, and volatility spikes.
    """
    def __init__(self):
        self._cache: Dict[str, List[Dict[str, Any]]] = {}

    def get_or_generate_rates(self, symbol: str, timeframe: str, count: int = 500) -> List[Dict[str, Any]]:
        cache_key = f"{symbol}_{timeframe}"
        minutes = TIMEFRAME_MINUTES.get(timeframe, 15)
        step_delta = timedelta(minutes=minutes)
        
        now = datetime.now(timezone.utc)
        # Snap to recent closed bar
        end_time = now - timedelta(minutes=(now.minute % minutes), seconds=now.second, microseconds=now.microsecond)
        
        if cache_key in self._cache and len(self._cache[cache_key]) >= count:
            rates = self._cache[cache_key]
            # If the last candle is older than the current bar, append a new candle
            last_candle_time = datetime.fromtimestamp(rates[-1]["time"], tz=timezone.utc)
            if end_time > last_candle_time:
                prev_close = rates[-1]["close"]
                volatility = prev_close * (0.0015 if "USD" in symbol and symbol != "XAUUSD" else 0.003)
                drift = random.uniform(-0.002, 0.002) * prev_close
                c_open = prev_close
                c_close = c_open + drift + random.gauss(0, volatility)
                c_high = max(c_open, c_close) + abs(random.gauss(0, volatility * 0.6))
                c_low = min(c_open, c_close) - abs(random.gauss(0, volatility * 0.6))
                c_vol = round(random.uniform(500, 3000), 2)
                rates.append({
                    "time": int(end_time.timestamp()),
                    "open": round(c_open, 4),
                    "high": round(c_high, 4),
                    "low": round(c_low, 4),
                    "close": round(c_close, 4),
                    "tick_volume": c_vol
                })
                if len(rates) > count + 200:
                    rates = rates[-count:]
                self._cache[cache_key] = rates
            return rates[-count:]

        # Seed realistic historical series
        base_price = BASE_PRICES.get(symbol.upper(), 100.0)
        volatility = base_price * (0.0012 if "USD" in symbol and symbol != "XAUUSD" and symbol != "BTCUSD" else 0.0025)
        
        rates = []
        curr_price = base_price
        trend_phase = 0
        trend_direction = random.choice([1, -1])

        start_time = end_time - (step_delta * count)
        for i in range(count):
            c_time = start_time + (step_delta * i)
            # Cycle through trend and consolidation phases
            if i % 30 == 0:
                trend_direction = random.choice([1, -1, 0])
            
            drift = trend_direction * (volatility * 0.25)
            c_open = curr_price
            c_close = c_open + drift + random.gauss(0, volatility)
            c_high = max(c_open, c_close) + abs(random.gauss(0, volatility * 0.7))
            c_low = min(c_open, c_close) - abs(random.gauss(0, volatility * 0.7))
            c_vol = round(random.uniform(300, 2500), 2)

            curr_price = c_close
            rates.append({
                "time": int(c_time.timestamp()),
                "open": round(c_open, 4),
                "high": round(c_high, 4),
                "low": round(c_low, 4),
                "close": round(c_close, 4),
                "tick_volume": c_vol
            })

        self._cache[cache_key] = rates
        return rates


class MockSymbol:
    def __init__(self, name: str):
        self.name = name


class MT5Adapter:
    """
    Unified MT5 Interface. Auto-detects terminal availability and provides
    seamless fallback to SyntheticMarketFeed.
    """
    def __init__(self):
        self._is_initialized = False
        self._is_synthetic = False
        self._synthetic_feed = SyntheticMarketFeed()
        self._last_error = "None"

    @property
    def is_synthetic(self) -> bool:
        return self._is_synthetic

    def initialize(self, login: Optional[int] = None, password: Optional[str] = None, server: Optional[str] = None) -> bool:
        if not MT5_AVAILABLE or mt5 is None:
            self._is_synthetic = True
            self._is_initialized = True
            logger.info("MT5 Native C-extension not available. Initialized in SYNTHETIC SIMULATION mode.")
            return True

        try:
            success = False
            if login and password and server:
                success = mt5.initialize(login=int(login), password=password, server=server)
            else:
                success = mt5.initialize()

            if success:
                self._is_synthetic = False
                self._is_initialized = True
                self._last_error = "None"
                logger.info("MT5 Native terminal connection established successfully.")
                return True
            else:
                err = mt5.last_error()
                self._last_error = str(err)
                logger.warning(f"MT5 terminal initialization failed ({err}). Gracefully falling back to SYNTHETIC SIMULATION mode.")
                self._is_synthetic = True
                self._is_initialized = True
                return True
        except Exception as ex:
            self._last_error = str(ex)
            logger.warning(f"MT5 initialization exception: {ex}. Falling back to SYNTHETIC SIMULATION mode.")
            self._is_synthetic = True
            self._is_initialized = True
            return True

    def shutdown(self):
        if MT5_AVAILABLE and mt5 is not None and not self._is_synthetic:
            try:
                mt5.shutdown()
            except Exception:
                pass
        self._is_initialized = False

    def last_error(self) -> str:
        if not self._is_synthetic and MT5_AVAILABLE and mt5 is not None:
            try:
                return str(mt5.last_error())
            except Exception:
                pass
        return self._last_error

    def symbols_get(self) -> List[Any]:
        if not self._is_synthetic and MT5_AVAILABLE and mt5 is not None:
            try:
                symbols = mt5.symbols_get()
                if symbols:
                    return list(symbols)
            except Exception as e:
                logger.warning(f"Error fetching symbols from native MT5: {e}")
        
        # Return standard synthetic symbols
        all_symbols = list(BASE_PRICES.keys()) + ["EURGBP", "EURJPY", "GBPJPY", "AUDUSD", "USDCAD", "USDCHF", "XAGUSD"]
        return [MockSymbol(s) for s in all_symbols]

    def symbol_select(self, symbol: str, enable: bool = True) -> bool:
        if not self._is_synthetic and MT5_AVAILABLE and mt5 is not None:
            try:
                return bool(mt5.symbol_select(symbol, enable))
            except Exception:
                return True
        return True

    def copy_rates_from_pos(self, symbol: str, timeframe: Union[int, str], start_pos: int = 0, count: int = 500) -> Optional[List[Dict[str, Any]]]:
        tf_str = timeframe if isinstance(timeframe, str) else "M15"
        for name, val in TIMEFRAME_NAME_TO_INT.items():
            if val == timeframe:
                tf_str = name
                break

        if not self._is_synthetic and MT5_AVAILABLE and mt5 is not None:
            try:
                tf_int = timeframe if isinstance(timeframe, int) else TIMEFRAME_NAME_TO_INT.get(timeframe, TIMEFRAME_M15)
                rates = mt5.copy_rates_from_pos(symbol, tf_int, start_pos, count)
                if rates is not None and len(rates) > 0:
                    # Convert numpy recarray or dicts to uniform list of dicts
                    res = []
                    for r in rates:
                        res.append({
                            "time": int(r["time"]),
                            "open": float(r["open"]),
                            "high": float(r["high"]),
                            "low": float(r["low"]),
                            "close": float(r["close"]),
                            "tick_volume": float(r["tick_volume"])
                        })
                    return res
                else:
                    logger.warning(f"Native MT5 copy_rates returned empty for {symbol}. Falling back to synthetic rates.")
            except Exception as e:
                logger.warning(f"Native MT5 copy_rates error: {e}. Using synthetic fallback.")

        # Return synthetic rates
        return self._synthetic_feed.get_or_generate_rates(symbol, tf_str, count)


# Global singleton instance
adapter = MT5Adapter()
