# Reference: CLI Command-Line Interface

Meta-Marker provides a unified command-line tool accessible via `meta-marker` or `python -m src.cli`.

---

## 1. Global Syntax

```bash
meta-marker [COMMAND] [OPTIONS]
```

Or via UV runner:
```bash
uv run meta-marker [COMMAND] [OPTIONS]
```

---

## 2. Commands

### `serve`
Launches the FastAPI unified gateway server, background MT5/synthetic sync worker, and static web cockpit.

```bash
uv run meta-marker serve [--host HOST] [--port PORT] [--reload]
```

| Option | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `--host` | string | `127.0.0.1` | Network interface to bind to |
| `--port` | integer | `8000` | Port to listen on |
| `--reload` | flag | `false` | Enable hot-reloading for development |

---

### `classify`
Performs a one-shot deterministic market classification on any symbol and timeframe, outputting regime states, indicator matrix breakdown, and trade setups.

```bash
uv run meta-marker classify [--symbol SYMBOL] [--timeframe TIMEFRAME]
```

| Option | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `--symbol` | string | `XAUUSD` | Target asset symbol (e.g. `BTCUSD`, `EURUSD`) |
| `--timeframe` | string | `M15` | Candle bar timeframe (`M1`, `M5`, `M15`, `H1`, `D1`) |

---

### `audit`
Queries the persistent prediction audit ledger and displays win-rate metrics, resolved TP/SL counts, and recent trade records.

```bash
uv run meta-marker audit [--symbol SYMBOL] [--limit LIMIT]
```

| Option | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `--symbol` | string | `None` | Filter predictions by specific symbol |
| `--limit` | integer | `20` | Maximum number of records to display |

---

### `health`
Inspects the local engine state, bridge mode (`LIVE_MT5` vs `SYNTHETIC_SIMULATION`), active monitored symbols, and database readiness.

```bash
uv run meta-marker health
```
