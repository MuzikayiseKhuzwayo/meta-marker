"""
Meta-Marker CLI - Unified Command-Line Interface for the Market Intelligence Engine.
"""

import argparse
import sys
import os
import json
from datetime import datetime, timezone

# Ensure Unicode output on Windows console
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

def run_serve(args):
    import uvicorn
    print(f"\n=======================================================")
    print(f"  META-MARKER MARKET INTELLIGENCE ENGINE (MIE)")
    print(f"  Serving Unified Gateway on http://{args.host}:{args.port}")
    print(f"=======================================================\n")
    uvicorn.run("src.api.main:app", host=args.host, port=args.port, reload=args.reload)

def run_classify(args):
    from src.engine.db import Database
    from src.engine.classifier import MarketClassifier
    from src.engine.mt5_adapter import adapter

    symbol = args.symbol.upper()
    timeframe = args.timeframe.upper()

    print(f"\n--- Meta-Marker Classification: {symbol} [{timeframe}] ---")
    db = Database()
    classifier = MarketClassifier(db)

    # Ingest or fetch candles
    candles = db.get_candles(symbol=symbol, timeframe=timeframe, limit=500)
    if len(candles) < 50:
        print(f"[!] Insufficient candles in local DB ({len(candles)}). Fetching from adapter...")
        adapter.initialize()
        rates = adapter.copy_rates_from_pos(symbol, timeframe, 0, 500)
        if rates:
            from src.engine.models import Candle
            for r in rates:
                c = Candle(
                    time=datetime.fromtimestamp(r["time"], tz=timezone.utc),
                    open=r["open"], high=r["high"], low=r["low"], close=r["close"],
                    volume=r["tick_volume"], symbol=symbol, timeframe=timeframe
                )
                db.save_candle(c)
            candles = db.get_candles(symbol=symbol, timeframe=timeframe, limit=500)

    if len(candles) < 50:
        print(f"[ERROR] Could not gather sufficient data for {symbol} ({timeframe}).")
        return

    result = classifier.classify(candles)
    print(f"Price (Close):     {result.candle.close}")
    print(f"Primary Regime:    {result.classification.primary_regime}")
    print(f"Trend State:       {result.classification.trend_state}")
    print(f"Volatility:        {result.classification.volatility_state}")
    print(f"Momentum:          {result.classification.momentum_state}")
    print(f"Buy Confidence:    {result.confidence_buy:.1f}%")
    print(f"Sell Confidence:   {result.confidence_sell:.1f}%")
    print(f"Recommendation:    {result.recommendation}")
    if result.trade_setup:
        print(f"\n--- Active Trade Setup ---")
        print(f"Entry:             {result.trade_setup.entry:.2f}")
        print(f"Stop Loss:         {result.trade_setup.stop_loss:.2f}")
        print(f"Take Profit:       {result.trade_setup.take_profit:.2f}")
        print(f"Kelly Risk Sizing: {result.trade_setup.kelly_percentage:.1f}%")

    print(f"\n--- Indicator Matrix Breakdown ---")
    for name, sig in result.indicator_signals.items():
        print(f"  {name:<18} | Signal: {sig.signal:<7} | Value: {sig.value:>9.3f} | Reliability: {sig.confidence*100:>5.1f}%")

def run_audit(args):
    from src.engine.db import Database
    db = Database()
    history = db.get_recent_predictions(symbol=args.symbol, limit=args.limit)
    total = len(history)
    resolved = [p for p in history if p["status"] in ("SUCCESS_TP", "FAIL_SL")]
    wins = [p for p in resolved if p["status"] == "SUCCESS_TP"]
    win_rate = (len(wins) / len(resolved) * 100.0) if resolved else 0.0

    print(f"\n=======================================================")
    print(f"  META-MARKER PREDICTION AUDIT & RELIABILITY TELEMETRY")
    print(f"=======================================================")
    print(f"Total Audited Predictions: {total}")
    print(f"Resolved (TP or SL):       {len(resolved)}")
    print(f"Winning Trades (Hit TP):   {len(wins)}")
    print(f"Win-Rate:                  {win_rate:.1f}%\n")

    if history:
        print(f"{'ID':<5} | {'Symbol':<8} | {'TF':<4} | {'Regime':<18} | {'Status':<11} | {'Buy%':<6} | {'Sell%':<6}")
        print("-" * 72)
        for p in history[:args.limit]:
            print(f"{p['id']:<5} | {p['symbol']:<8} | {p['timeframe']:<4} | {p['primary_regime'][:18]:<18} | {p['status']:<11} | {p['buy_confidence']:>5.1f}% | {p['sell_confidence']:>5.1f}%")

def run_health(args):
    from src.engine.mt5_adapter import adapter
    from src.engine.db import Database
    db = Database()
    markets = db.get_monitored_markets()
    scores = db.get_indicator_scores()
    print(f"\n--- Meta-Marker Engine Diagnostics ---")
    print(f"Bridge Mode:       {'SYNTHETIC_SIMULATION' if adapter.is_synthetic else 'LIVE_MT5'}")
    print(f"Monitored Targets: {len(markets)} active pairs")
    print(f"Scored Indicators: {len(scores)} algorithm models")
    print(f"Database:          {db.db_path} (Ready)")

def main():
    parser = argparse.ArgumentParser(description="Meta-Marker Market Intelligence Engine CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Serve command
    p_serve = subparsers.add_parser("serve", help="Launch the unified FastAPI server & Cockpit")
    p_serve.add_argument("--host", default="127.0.0.1", help="Binding host (default: 127.0.0.1)")
    p_serve.add_argument("--port", type=int, default=8000, help="Port (default: 8000)")
    p_serve.add_argument("--reload", action="store_true", help="Enable auto-reload")
    p_serve.set_defaults(func=run_serve)

    # Classify command
    p_classify = subparsers.add_parser("classify", help="Run deterministic classification on a target")
    p_classify.add_argument("--symbol", default="XAUUSD", help="Symbol (default: XAUUSD)")
    p_classify.add_argument("--timeframe", default="M15", help="Timeframe (default: M15)")
    p_classify.set_defaults(func=run_classify)

    # Audit command
    p_audit = subparsers.add_parser("audit", help="Inspect real-time prediction audit and win-rate log")
    p_audit.add_argument("--symbol", default=None, help="Filter by symbol")
    p_audit.add_argument("--limit", type=int, default=20, help="Max entries to show")
    p_audit.set_defaults(func=run_audit)

    # Health command
    p_health = subparsers.add_parser("health", help="Check engine status and bridge mode")
    p_health.set_defaults(func=run_health)

    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
