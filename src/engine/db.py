import sqlite3
import os
import json
from datetime import datetime
from typing import List, Dict, Tuple, Optional, Any
from .models import Candle, MarketClassification

DB_FILE = "meta_marker.db"

class Database:
    def __init__(self, db_path: str = DB_FILE):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        if self.db_path == ":memory:":
            if not hasattr(self, "_conn") or self._conn is None:
                self._conn = sqlite3.connect(self.db_path)
            return self._conn
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Create candles table supporting multi-symbol and multi-timeframe
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS candles (
                    symbol TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    time TEXT NOT NULL,
                    open REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    close REAL NOT NULL,
                    volume REAL NOT NULL,
                    PRIMARY KEY (symbol, timeframe, time)
                )
            """)
            
            # Create indicator_scores table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS indicator_scores (
                    indicator_name TEXT NOT NULL,
                    regime TEXT NOT NULL,
                    score REAL DEFAULT 50.0,
                    num_predictions INTEGER DEFAULT 0,
                    num_correct INTEGER DEFAULT 0,
                    PRIMARY KEY (indicator_name, regime)
                )
            """)
            
            # Create classifications table supporting multi-symbol and multi-timeframe
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS classifications (
                    symbol TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    time TEXT NOT NULL,
                    trend_state TEXT NOT NULL,
                    volatility_state TEXT NOT NULL,
                    momentum_state TEXT NOT NULL,
                    primary_regime TEXT NOT NULL,
                    PRIMARY KEY (symbol, timeframe, time)
                )
            """)
            
            # Create monitored_markets table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS monitored_markets (
                    symbol TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    added_at TEXT NOT NULL,
                    is_active INTEGER DEFAULT 1,
                    PRIMARY KEY (symbol, timeframe)
                )
            """)

            # Create prediction_audit table for real-time Dynamic Reliability tracking
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS prediction_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    primary_regime TEXT NOT NULL,
                    recommendation TEXT NOT NULL,
                    buy_confidence REAL NOT NULL,
                    sell_confidence REAL NOT NULL,
                    entry_price REAL NOT NULL,
                    stop_loss REAL,
                    take_profit REAL,
                    indicator_signals TEXT NOT NULL,
                    status TEXT DEFAULT 'PENDING',
                    resolved_at TEXT,
                    resolved_price REAL
                )
            """)
            
            # Seed default famous markets if empty
            cursor.execute("SELECT COUNT(*) FROM monitored_markets")
            if cursor.fetchone()[0] == 0:
                defaults = [
                    ("XAUUSD", "M15"),
                    ("EURUSD", "M15"),
                    ("GBPUSD", "M15"),
                    ("BTCUSD", "M15"),
                    ("NAS100", "M15")
                ]
                now_str = datetime.utcnow().isoformat()
                for sym, tf in defaults:
                    cursor.execute("""
                        INSERT OR IGNORE INTO monitored_markets (symbol, timeframe, added_at, is_active)
                        VALUES (?, ?, ?, 1)
                    """, (sym, tf, now_str))

            conn.commit()

    def save_candle(self, candle: Candle):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO candles (symbol, timeframe, time, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                candle.symbol,
                candle.timeframe,
                candle.time.isoformat(),
                candle.open,
                candle.high,
                candle.low,
                candle.close,
                candle.volume
            ))
            conn.commit()

    def get_candles(self, symbol: str = "XAUUSD", timeframe: str = "M15", limit: int = 500) -> List[Candle]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT time, open, high, low, close, volume, symbol, timeframe
                FROM candles 
                WHERE symbol = ? AND timeframe = ?
                ORDER BY time ASC 
                LIMIT ?
            """, (symbol, timeframe, limit))
            rows = cursor.fetchall()
            
            candles = []
            for r in rows:
                candles.append(Candle(
                    time=datetime.fromisoformat(r[0]),
                    open=r[1],
                    high=r[2],
                    low=r[3],
                    close=r[4],
                    volume=r[5],
                    symbol=r[6],
                    timeframe=r[7]
                ))
            return candles

    def save_classification(self, timestamp: datetime, classification: MarketClassification, symbol: str = "XAUUSD", timeframe: str = "M15"):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO classifications (symbol, timeframe, time, trend_state, volatility_state, momentum_state, primary_regime)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                symbol,
                timeframe,
                timestamp.isoformat(),
                classification.trend_state,
                classification.volatility_state,
                classification.momentum_state,
                classification.primary_regime
            ))
            conn.commit()

    def get_latest_classification(self, symbol: str = "XAUUSD", timeframe: str = "M15") -> Optional[MarketClassification]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT trend_state, volatility_state, momentum_state, primary_regime 
                FROM classifications 
                WHERE symbol = ? AND timeframe = ?
                ORDER BY time DESC 
                LIMIT 1
            """)
            row = cursor.fetchone()
            if row:
                return MarketClassification(
                    trend_state=row[0],
                    volatility_state=row[1],
                    momentum_state=row[2],
                    primary_regime=row[3]
                )
            return None

    def get_indicator_scores(self) -> Dict[str, Dict[str, float]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT indicator_name, regime, score FROM indicator_scores")
            rows = cursor.fetchall()
            
            scores = {}
            for row in rows:
                ind_name, regime, score = row
                if ind_name not in scores:
                    scores[ind_name] = {}
                scores[ind_name][regime] = score
            return scores

    def update_indicator_score(self, indicator_name: str, regime: str, is_correct: bool):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT score, num_predictions, num_correct 
                FROM indicator_scores 
                WHERE indicator_name = ? AND regime = ?
            """, (indicator_name, regime))
            row = cursor.fetchone()
            
            if row:
                score, num_preds, num_corr = row
                num_preds += 1
                if is_correct:
                    num_corr += 1
                new_score = (num_corr / num_preds) * 100.0
            else:
                num_preds = 1
                num_corr = 1 if is_correct else 0
                new_score = 100.0 if is_correct else 0.0
                
            cursor.execute("""
                INSERT OR REPLACE INTO indicator_scores (indicator_name, regime, score, num_predictions, num_correct)
                VALUES (?, ?, ?, ?, ?)
            """, (indicator_name, regime, new_score, num_preds, num_corr))
            conn.commit()

    def add_monitored_market(self, symbol: str, timeframe: str):
        symbol = symbol.upper()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO monitored_markets (symbol, timeframe, added_at, is_active)
                VALUES (?, ?, ?, 1)
            """, (symbol, timeframe, datetime.utcnow().isoformat()))
            conn.commit()

    def get_monitored_markets(self) -> List[Dict[str, str]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT symbol, timeframe FROM monitored_markets WHERE is_active = 1")
            rows = cursor.fetchall()
            return [{"symbol": row[0], "timeframe": row[1]} for row in rows]

    def remove_monitored_market(self, symbol: str, timeframe: str):
        symbol = symbol.upper()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE monitored_markets SET is_active = 0 WHERE symbol = ? AND timeframe = ?
            """, (symbol, timeframe))
            conn.commit()

    def save_prediction(self, symbol: str, timeframe: str, primary_regime: str, recommendation: str, 
                        buy_conf: float, sell_conf: float, entry_price: float, 
                        stop_loss: Optional[float], take_profit: Optional[float], 
                        indicator_signals: Dict[str, Any]) -> int:
        symbol = symbol.upper()
        now_str = datetime.utcnow().isoformat()
        signals_json = json.dumps(indicator_signals)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO prediction_audit (symbol, timeframe, timestamp, primary_regime, recommendation, buy_confidence, sell_confidence, entry_price, stop_loss, take_profit, indicator_signals, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING')
            """, (symbol, timeframe, now_str, primary_regime, recommendation, buy_conf, sell_conf, entry_price, stop_loss, take_profit, signals_json))
            conn.commit()
            return cursor.lastrowid

    def get_pending_predictions(self, symbol: str, timeframe: str) -> List[Dict[str, Any]]:
        symbol = symbol.upper()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, symbol, timeframe, timestamp, primary_regime, recommendation, buy_confidence, sell_confidence, entry_price, stop_loss, take_profit, indicator_signals, status
                FROM prediction_audit
                WHERE symbol = ? AND timeframe = ? AND status = 'PENDING'
            """, (symbol, timeframe))
            rows = cursor.fetchall()
            results = []
            for r in rows:
                results.append({
                    "id": r[0],
                    "symbol": r[1],
                    "timeframe": r[2],
                    "timestamp": r[3],
                    "primary_regime": r[4],
                    "recommendation": r[5],
                    "buy_confidence": r[6],
                    "sell_confidence": r[7],
                    "entry_price": r[8],
                    "stop_loss": r[9],
                    "take_profit": r[10],
                    "indicator_signals": json.loads(r[11]),
                    "status": r[12]
                })
            return results

    def resolve_prediction(self, pred_id: int, status: str, resolved_price: float):
        now_str = datetime.utcnow().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE prediction_audit
                SET status = ?, resolved_at = ?, resolved_price = ?
                WHERE id = ?
            """, (status, now_str, resolved_price, pred_id))
            conn.commit()

    def get_recent_predictions(self, symbol: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if symbol:
                cursor.execute("""
                    SELECT id, symbol, timeframe, timestamp, primary_regime, recommendation, buy_confidence, sell_confidence, entry_price, stop_loss, take_profit, status, resolved_at, resolved_price
                    FROM prediction_audit
                    WHERE symbol = ?
                    ORDER BY id DESC LIMIT ?
                """, (symbol.upper(), limit))
            else:
                cursor.execute("""
                    SELECT id, symbol, timeframe, timestamp, primary_regime, recommendation, buy_confidence, sell_confidence, entry_price, stop_loss, take_profit, status, resolved_at, resolved_price
                    FROM prediction_audit
                    ORDER BY id DESC LIMIT ?
                """, (limit,))
            rows = cursor.fetchall()
            results = []
            for r in rows:
                results.append({
                    "id": r[0],
                    "symbol": r[1],
                    "timeframe": r[2],
                    "timestamp": r[3],
                    "primary_regime": r[4],
                    "recommendation": r[5],
                    "buy_confidence": r[6],
                    "sell_confidence": r[7],
                    "entry_price": r[8],
                    "stop_loss": r[9],
                    "take_profit": r[10],
                    "status": r[11],
                    "resolved_at": r[12],
                    "resolved_price": r[13]
                })
            return results
