# Meta-Marker (Market Intelligence Engine)

Meta-Marker is a **Market Intelligence Engine (MIE)** designed to classify market conditions (Trend vs. Range, Volatility, Momentum) for trading Gold (XAU/USD) on the M15 timeframe. Instead of relying on static indicators, Meta-Marker dynamically calculates, weighs, and scores multiple indicators based on their real-time and historical performance in specific market states.

## Key Features

- **Dynamic Indicator Scoring**: Automatically tracks prediction accuracy of indicators (EMAs, RSI, MACD, Stochastic, Market Structure/BOS) and adjusts their weights dynamically depending on the current regime (Trend vs. Range).
- **Market Classification**: Classifies market states into regimes such as *Strong Uptrend*, *Strong Downtrend*, *Ranging (Choppy)*, *Ranging (Tight)*, and *Expanding Volatility*.
- **Direct MetaTrader 5 (MT5) Integration**: Built-in background sync worker that pulls M15 bars directly from your local MT5 terminal via python `MetaTrader5` package.
- **Premium Glassmorphic Dashboard**: A stunning cyber-dark web dashboard visualizing overall buy/sell confidence, regime details, real-time OHLC candlestick chart, and the indicator performance matrix.

---

## System Architecture

```
                       ┌─────────────────────────┐
                       │  Local MT5 Desktop App  │
                       └────────────┬────────────┘
                                    │ (Direct Sync Loop)
                                    ▼
                       ┌─────────────────────────┐
                       │  Market Intel Engine    │
                       │   (Python / FastAPI)    │
                       └────────────┬────────────┘
                                    │
         ┌──────────────────────────┼──────────────────────────┐
         ▼                          ▼                          ▼
┌─────────────────┐        ┌─────────────────┐        ┌─────────────────┐
│ SQLite Database │        │ Scorer & Weights│        │ Web UI Router   │
│  (meta_marker)  │        │  (classifier)   │        │   (dashboard)   │
└─────────────────┘        └─────────────────┘        └─────────────────┘
```

---

## Installation & Setup

### 1. Prerequisites
- **Operating System**: Windows (required by the `MetaTrader5` Python package).
- **MetaTrader 5**: Installed and running locally.
- **Python**: version `3.9+` (installed via `uv` package manager).

### 2. Configure DLL Imports in MT5
The Python package communicates with MT5 via a local DLL socket channel.
1. Open your MT5 terminal GUI.
2. Go to **Tools** ➔ **Options** (or press `Ctrl + O`).
3. Select the **Expert Advisors** tab.
4. Check **`Allow DLL imports`**.
5. Click **OK** to save and apply.

### 3. Clone & Initialize Environment
Clone the repository and install dependencies using `uv`:
```bash
# Install dependencies and create virtual environment
uv sync
```

### 4. Configure Credentials (`.env`)
Create a `.env` file in the project root to configure your MT5 login (if your terminal requires explicit credentials authentication):
```env
MT5_LOGIN=your_demo_account_number
MT5_PASSWORD=your_demo_password
MT5_SERVER=MetaQuotes-Demo
```
*Note: If your opened MT5 GUI is already logged in, you can omit these variables and the script will automatically connect to the active GUI terminal.*

---

## Running the Application

1. Ensure your **MT5 GUI terminal** is open and logged into your account.
2. Start the FastAPI backend and sync worker:
   ```bash
   uv run uvicorn src.api.main:app --reload
   ```
3. Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your web browser to access the dashboard.

---

## Testing

Run unit tests covering technical indicators (SMA, EMA, RSI, ATR) using `pytest`:
```bash
uv run python -m pytest
```

---

## License

This project is licensed under the [MIT License](LICENSE).
