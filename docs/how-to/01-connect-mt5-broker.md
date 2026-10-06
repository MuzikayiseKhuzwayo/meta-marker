# How-To Guide: Connect Live MetaTrader 5 Broker Feeds

This recipe explains how to configure and link a live or demo MetaTrader 5 (MT5) terminal with the Meta-Marker engine on Windows.

---

## Step 1: Enable DLL Imports in MT5 Terminal

Meta-Marker communicates with the MT5 terminal via the official Python C-extension socket DLL.

1. Open your **MetaTrader 5 GUI application**.
2. Press `Ctrl + O` or navigate to **Tools** ➔ **Options**.
3. Select the **Expert Advisors** tab.
4. Check **`Allow DLL imports`**.
5. *(Optional)* Check **`Allow algorithmic trading`**.
6. Click **OK** to save changes.

---

## Step 2: Configure Environment Credentials (`.env`)

If your MT5 terminal requires explicit credentials authentication upon initialization:

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
2. Edit `.env` with your broker details:
   ```env
   MT5_LOGIN=12345678
   MT5_PASSWORD=YourPasswordHere
   MT5_SERVER=MetaQuotes-Demo
   ```

> **Note:** If your MT5 terminal is already logged into an active broker account and running on your desktop, you can leave these credentials blank. Meta-Marker's adapter will automatically connect to the active GUI session!

---

## Step 3: Verify Terminal Connectivity

Verify that the engine recognizes the native MT5 terminal:

```bash
uv run meta-marker health
```

Expected Output:
```
--- Meta-Marker Engine Diagnostics ---
Bridge Mode:       LIVE_MT5
Monitored Targets: 10 active pairs
Scored Indicators: 5 algorithm models
Database:          meta_marker.db (Ready)
```

---

## Step 4: Add New Broker Symbols to Monitor

To monitor a custom symbol (e.g. `USOIL` or `GER40`):

1. Via the Web Cockpit:
   - Type the symbol name into the **Add Symbol** box in the header and click `+`.
2. Via the REST API:
   ```bash
   curl -X POST http://127.0.0.1:8000/api/monitor/add \
        -H "Content-Type: application/json" \
        -d '{"symbol": "USOIL", "timeframe": "M15"}'
   ```
3. The background sync worker will automatically query the broker's market watch, download the latest 1,000 bars, and initialize dynamic scoring.
