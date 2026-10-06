# How-To Guide: Running in Headless & Synthetic Simulation Mode

This guide explains how to deploy and operate Meta-Marker in environments without a Windows GUI or MetaTrader 5 installed (e.g., Linux servers, Docker containers, macOS development environments, or CI/CD pipelines).

---

## 1. Automatic Fallback Architecture

Meta-Marker features a zero-configuration fallback bridge (`src/engine/mt5_adapter.py`):
- **On Windows with MT5**: Automatically connects to native MT5 via DLL socket.
- **On Linux / macOS / Headless**: Seamlessly activates `SyntheticMarketFeed` with zero runtime crashes.

---

## 2. Booting the Server in Docker or Linux

To run the unified server in a container or Linux virtual machine:

```bash
# Clone and enter repo
git clone https://github.com/MuzikayiseKhuzwayo/meta-marker.git
cd meta-marker

# Install requirements via uv
uv sync

# Launch the gateway
uv run meta-marker serve --host 0.0.0.0 --port 8000
```

Verify the synthetic bridge is active:
```bash
curl http://127.0.0.1:8000/api/health
```

Response:
```json
{
  "status": "healthy",
  "mode": "SYNTHETIC_SIMULATION",
  "is_synthetic": true,
  "active_targets": [
    {"symbol": "XAUUSD", "timeframe": "M15"},
    {"symbol": "BTCUSD", "timeframe": "M15"}
  ],
  "database": "meta_marker.db"
}
```

---

## 3. How the Synthetic Market Feed Works

The synthetic engine uses a **Geometric Brownian Motion** model with:
- Realistic drift based on multi-bar regime cycles.
- Volatility calibrated per asset class (Forex, Gold, Crypto, Indices).
- Live bar generation: as time elapses, new closed candles are emitted every timeframe interval, triggering closed-bar scoring and prediction audits.

---

## 4. Running Headless Unit Tests in CI/CD

To integrate Meta-Marker into GitHub Actions or GitLab CI:

```yaml
name: Test Suite
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install uv
        uses: astral-sh/setup-uv@v3
      - name: Set up Python
        run: uv python install 3.9
      - name: Install dependencies
        run: uv sync
      - name: Run pytest
        run: uv run pytest
```
All tests pass in headless Linux without any MT5 binaries.
