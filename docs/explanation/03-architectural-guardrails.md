# Explanation: Architectural Guardrails & Determinism

This document outlines the core engineering philosophy, architectural guardrails, and deterministic principles governing Meta-Marker.

---

## 1. The Core Philosophy: Determinism Over Hallucination

In algorithmic finance, non-deterministic systems (such as direct generative LLM inference for trade execution) introduce catastrophic non-reproducibility and latency jitter.

Meta-Marker adheres strictly to **deterministic execution**:
- **Pure Mathematical Calculations:** Technical indicators (SMA, EMA, RSI, MACD, ADX, ATR, Stochastic) are implemented as stateless, deterministic algorithms with mathematical unit tests.
- **Closed-Bar Evaluation:** Predictions are only audited upon the timestamp confirmation of a completed candle close, eliminating repainting and lookahead bias.
- **Persistent Auditability:** Every classification and actionable signal is recorded with its initial entry, SL, TP, and contributing indicator weights to an immutable SQLite ledger.

---

## 2. Universal Portability & Graceful Degradation

```
                  ┌──────────────────────────────┐
                  │      Meta-Marker Gateway     │
                  └──────────────┬───────────────┘
                                 │
                   Can connect to Windows MT5?
                                 │
                ┌────────────────┴────────────────┐
             YES│                                 │NO
                ▼                                 ▼
      ┌──────────────────┐              ┌──────────────────┐
      │  Native Windows  │              │    Synthetic     │
      │  MT5 Terminal    │              │  Brownian Motion │
      │   (Live Feed)    │              │ (Simulation Replay)
      └──────────────────┘              └──────────────────┘
```

1. **Zero-Crash Portability:** The engine boots successfully on any OS (Windows, Linux, macOS, Alpine, Docker). If native MT5 libraries or desktop terminals are not present, the `MT5Adapter` transparently routes to `SyntheticMarketFeed`.
2. **First-Class API & CLI:** Every function exposed via the web cockpit is available identically via REST endpoints and terminal CLI subcommands.
3. **Single Port Gateway:** Presentation UI, WebSockets, REST APIs, and file exports are mounted on a single configurable port (default `8000`), eliminating multi-port orchestration friction.
