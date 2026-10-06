# Reference: REST & WebSocket API Specification

This document provides a machine-accurate specification of the Meta-Marker Gateway API endpoints and WebSocket streaming protocol.

**Base URL:** `http://127.0.0.1:8000`  
**WebSocket URL:** `ws://127.0.0.1:8000/ws`  
**Format:** JSON  

---

## 1. System Health & Diagnostics

### `GET /api/health`
Returns the operational health and active bridge status of the engine.

**Response (200 OK):**
```json
{
  "status": "healthy",
  "mode": "LIVE_MT5",
  "is_synthetic": false,
  "active_targets": [
    {"symbol": "XAUUSD", "timeframe": "M15"}
  ],
  "database": "meta_marker.db",
  "timestamp": "2026-10-06T11:40:00.000000Z"
}
```

### `GET /api/diagnostics`
Returns real-time process memory footprint, CPU utilization, and database ledger counts.

**Response (200 OK):**
```json
{
  "engine_mode": "LIVE_MT5",
  "process": {
    "memory_rss_mb": 45.2,
    "cpu_percent": 1.2
  },
  "monitored_targets_count": 5,
  "indicators_scored_count": 5,
  "recent_predictions_count": 24,
  "last_adapter_error": "None"
}
```

---

## 2. Market State & Telemetry

### `GET /api/state`
Queries the complete deterministic market intelligence response for a given symbol and timeframe.

**Parameters:**
| Name | Type | In | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `symbol` | string | query | No | `XAUUSD` | Target asset symbol |
| `timeframe` | string | query | No | `M15` | Target bar timeframe |

**Response (200 OK):**
```json
{
  "symbol": "XAUUSD",
  "timeframe": "M15",
  "candle": {
    "time": "2026-10-06T11:30:00Z",
    "open": 2350.1,
    "high": 2355.4,
    "low": 2349.8,
    "close": 2354.2,
    "volume": 1420.0
  },
  "classification": {
    "trend_state": "Strong Uptrend",
    "volatility_state": "Medium",
    "momentum_state": "Bullish",
    "primary_regime": "Trend Following"
  },
  "indicator_signals": {
    "EMA_Cross": {
      "name": "EMA_Cross",
      "value": 14.2,
      "signal": "BUY",
      "confidence": 0.85
    }
  },
  "confidence_buy": 82.4,
  "confidence_sell": 17.6,
  "recommendation": "STRONG BUY (82.4% confidence)",
  "trade_setup": {
    "entry": 2354.2,
    "stop_loss": 2342.1,
    "take_profit": 2378.4,
    "kelly_percentage": 3.2
  }
}
```

---

## 3. Monitoring & Target Management

### `GET /api/broker/symbols`
Returns all active symbols available in the connected broker terminal or synthetic feed.

### `GET /api/monitor/targets`
Returns the list of actively monitored symbols and timeframes.

### `POST /api/monitor/add`
Subscribes the sync worker to a new symbol and timeframe.
```json
{
  "symbol": "BTCUSD",
  "timeframe": "M15"
}
```

### `POST /api/monitor/remove`
Unsubscribes a symbol and timeframe from the active sync loop.

---

## 4. Prediction Audits & Data Export

### `GET /api/predictions/history`
Returns recent prediction entries, outcome statuses (`PENDING`, `SUCCESS_TP`, `FAIL_SL`), and overall win rate.

### `GET /api/export/audit.csv`
Streams the historical prediction audit log as a downloadable CSV file for quant research.

### `GET /api/export/candles`
Streams historical OHLCV candle records as JSON (`?symbol=XAUUSD&timeframe=M15&limit=1000`).

---

## 5. WebSocket Real-Time Channel (`/ws`)

Clients connect via `ws://127.0.0.1:8000/ws`.

Whenever a new candle is ingested and classified by the background worker, the server broadcasts the full `MarketStateResponse` JSON to all connected clients.
