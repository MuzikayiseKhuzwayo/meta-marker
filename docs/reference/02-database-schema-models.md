# Reference: Database Schema & Pydantic Data Models

This document details the persistent SQLite database tables and core Pydantic v2 data models utilized by the Meta-Marker engine.

---

## 1. SQLite Relational Schema (`meta_marker.db`)

### `candles` Table
Stores historical and live OHLCV price action bars for all monitored symbols and timeframes.
```sql
CREATE TABLE candles (
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    time TEXT NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume REAL NOT NULL,
    PRIMARY KEY (symbol, timeframe, time)
);
```

### `indicator_scores` Table
Stores the historical accuracy and dynamic scoring weights for each indicator per market regime.
```sql
CREATE TABLE indicator_scores (
    indicator_name TEXT NOT NULL,
    regime TEXT NOT NULL,
    score REAL DEFAULT 50.0,
    num_predictions INTEGER DEFAULT 0,
    num_correct INTEGER DEFAULT 0,
    PRIMARY KEY (indicator_name, regime)
);
```

### `classifications` Table
Records the historical market classification timeline for every closed candle bar.
```sql
CREATE TABLE classifications (
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    time TEXT NOT NULL,
    trend_state TEXT NOT NULL,
    volatility_state TEXT NOT NULL,
    momentum_state TEXT NOT NULL,
    primary_regime TEXT NOT NULL,
    PRIMARY KEY (symbol, timeframe, time)
);
```

### `prediction_audit` Table
The real-time audit ledger tracking every actionable trade signal, its initial parameters, and its subsequent resolution.
```sql
CREATE TABLE prediction_audit (
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
);
```

---

## 2. Pydantic Core Models ([`src/engine/models.py`](file:///c:/Users/muzik/Documents/GitHub/meta-marker/src/engine/models.py))

### `Candle`
- `time: datetime` (UTC timestamp)
- `open: float`, `high: float`, `low: float`, `close: float`
- `volume: float`
- `symbol: str` (e.g. `XAUUSD`)
- `timeframe: str` (e.g. `M15`)

### `MarketClassification`
- `trend_state: str` (`Strong Uptrend`, `Strong Downtrend`, `Weak Uptrend`, `Weak Downtrend`, `Ranging (Choppy)`, `Ranging (Tight)`)
- `volatility_state: str` (`High`, `Medium`, `Low`)
- `momentum_state: str` (`Bullish`, `Bearish`, `Neutral`)
- `primary_regime: str` (`Trend Following`, `Mean Reversion`)

### `TradeSetup`
- `entry: float` (Target entry level)
- `stop_loss: float` (Calculated protective stop level)
- `take_profit: float` (Calculated target exit level, typically 2:1 R:R)
- `kelly_percentage: float` (Half-Kelly recommended risk allocation capped at 5.0%)

### `MarketStateResponse`
- Full unified response aggregating latest `candle`, `classification`, `indicator_signals`, `confidence_buy`, `confidence_sell`, `recommendation`, `history`, and `trade_setup`.
