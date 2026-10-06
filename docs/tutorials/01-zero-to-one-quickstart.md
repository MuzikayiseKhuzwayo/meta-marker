# Tutorial: Zero-to-One Quickstart with Meta-Marker

**Learning Goal:** Launch the Meta-Marker Market Intelligence Engine, monitor a market in real-time, view regime classifications, and execute your first programmatic analysis in under 10 minutes.

---

## 1. Prerequisites

Before starting, ensure you have:
- **Python 3.9+** installed on your system.
- **[uv](https://github.com/astral-sh/uv)** installed (recommended for sub-second virtualenv setup):
  ```bash
  # Windows (PowerShell)
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```
- *(Optional)* **MetaTrader 5 Desktop Terminal** (if you want live broker tick feeds; otherwise, Meta-Marker automatically runs in **Synthetic Simulation Mode**).

---

## 2. Installation in 60 Seconds

Clone the repository and synchronize the environment:

```bash
git clone https://github.com/MuzikayiseKhuzwayo/meta-marker.git
cd meta-marker

# Install all dependencies into an isolated virtual environment
uv sync
```

---

## 3. Launch the Unified Cockpit

Start the FastAPI unified gateway and live web cockpit:

```bash
uv run meta-marker serve --port 8000
```

Open your browser to:
👉 **[http://127.0.0.1:8000](http://127.0.0.1:8000)**

You will see:
1. **Live Radar**: Real-time candlestick chart with draggable pan/zoom, 20 & 50 period EMAs, and detected support/resistance levels.
2. **Market Classification**: Current primary regime (Trend Following vs. Mean Reversion), volatility, and momentum state.
3. **Confidence Dial**: Dual-arc buy/sell consensus computed from weighted indicator reliability.
4. **Indicator Matrix**: Dynamic scoring table tracking empirical win-rates.

---

## 4. Run a Headless One-Shot Classification

To classify Gold (`XAUUSD`) or Bitcoin (`BTCUSD`) directly from the command line without opening a browser:

```bash
uv run meta-marker classify --symbol XAUUSD --timeframe M15
```

Example Output:
```
--- Meta-Marker Classification: XAUUSD [M15] ---
Price (Close):     2354.20
Primary Regime:    Trend Following
Trend State:       Strong Uptrend
Volatility:        Medium
Momentum:          Bullish
Buy Confidence:    82.4%
Sell Confidence:   17.6%
Recommendation:    STRONG BUY (82.4% confidence) - Trend continuation long breakout. | Entry: 2354.20 | SL: 2342.10 | TP: 2378.40 | Risk Sizing: 3.2% (Half-Kelly)
```

---

## 5. Next Steps

- Explore [How to Connect Live MT5 Broker Feeds](../how-to/01-connect-mt5-broker.md).
- Understand [Market Regime Theory & Indicators](../explanation/01-market-regime-theory.md).
- Review the [REST & WebSocket API Reference](../reference/01-rest-and-websocket-api.md).
