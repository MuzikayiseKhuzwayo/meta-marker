import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Tuple, Optional
from .models import Candle, MarketClassification

DB_FILE = "meta_marker.db"

class Database:
    def __init__(self, db_path: str = DB_FILE):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Create candles table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS candles (
                    time TEXT PRIMARY KEY,
                    open REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    close REAL NOT NULL,
                    volume REAL NOT NULL
                )
            """)
            
            # Create indicator_scores table (scored by market regime: trend or range)
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
            
            # Create classifications table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS classifications (
                    time TEXT PRIMARY KEY,
                    trend_state TEXT NOT NULL,
                    volatility_state TEXT NOT NULL,
                    momentum_state TEXT NOT NULL,
                    primary_regime TEXT NOT NULL
                )
            """)
            conn.commit()

    def save_candle(self, candle: Candle):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO candles (time, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                candle.time.isoformat(),
                candle.open,
                candle.high,
                candle.low,
                candle.close,
                candle.volume
            ))
            conn.commit()

    def get_candles(self, limit: int = 500) -> List[Candle]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT time, open, high, low, close, volume 
                FROM candles 
                ORDER BY time ASC 
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            
            candles = []
            for r in rows:
                candles.append(Candle(
                    time=datetime.fromisoformat(r[0]),
                    open=r[1],
                    high=r[2],
                    low=r[3],
                    close=r[4],
                    volume=r[5]
                ))
            return candles

    def save_classification(self, timestamp: datetime, classification: MarketClassification):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO classifications (time, trend_state, volatility_state, momentum_state, primary_regime)
                VALUES (?, ?, ?, ?, ?)
            """, (
                timestamp.isoformat(),
                classification.trend_state,
                classification.volatility_state,
                classification.momentum_state,
                classification.primary_regime
            ))
            conn.commit()

    def get_latest_classification(self) -> Optional[MarketClassification]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT trend_state, volatility_state, momentum_state, primary_regime 
                FROM classifications 
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
        """
        Returns scores in format: {indicator_name: {regime: score}}
        """
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
            # Select current values
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
                # Recalculate score (rolling average or simple accuracy percentage)
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
