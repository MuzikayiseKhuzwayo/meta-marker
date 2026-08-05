from src.engine.classifier import MarketClassifier
from src.engine.db import Database
from src.engine.models import Candle
from datetime import datetime
import pytest

def test_classifier_fallback():
    # Initialize DB (memory or temp)
    db = Database(":memory:")
    classifier = MarketClassifier(db)
    
    # Try classifying with empty list (n = 0 < 50)
    response = classifier.classify([])
    assert response.classification.trend_state == "Insufficient Data"
    assert response.confidence_buy == 50.0
    assert response.confidence_sell == 50.0
    assert "Please feed at least 50 historical candles" in response.recommendation
    assert response.candle.close == 0.0

def test_database_multi_symbol_timeframe():
    db = Database(":memory:")
    
    # Create candles for XAUUSD on M15
    c1 = Candle(time=datetime(2026, 8, 2, 12, 0), open=2000.0, high=2010.0, low=1990.0, close=2005.0, symbol="XAUUSD", timeframe="M15")
    # Create candle for BTCUSD on M5
    c2 = Candle(time=datetime(2026, 8, 2, 12, 0), open=60000.0, high=60100.0, low=59900.0, close=60050.0, symbol="BTCUSD", timeframe="M5")
    
    db.save_candle(c1)
    db.save_candle(c2)
    
    # Query XAUUSD M15
    res1 = db.get_candles(symbol="XAUUSD", timeframe="M15")
    assert len(res1) == 1
    assert res1[0].symbol == "XAUUSD"
    assert res1[0].timeframe == "M15"
    assert res1[0].close == 2005.0
    
    # Query BTCUSD M5
    res2 = db.get_candles(symbol="BTCUSD", timeframe="M5")
    assert len(res2) == 1
    assert res2[0].symbol == "BTCUSD"
    assert res2[0].timeframe == "M5"
    assert res2[0].close == 60050.0
    
    # Query BTCUSD M15 (should be empty)
    res3 = db.get_candles(symbol="BTCUSD", timeframe="M15")
    assert len(res3) == 0

def test_database_monitored_markets_persistence():
    db = Database(":memory:")
    
    # Default seeded markets on init
    markets = db.get_monitored_markets()
    symbols = [m["symbol"] for m in markets]
    assert "XAUUSD" in symbols
    assert "EURUSD" in symbols
    
    # Add new market
    db.add_monitored_market("USDJPY", "H1")
    updated = db.get_monitored_markets()
    pairs = [(m["symbol"], m["timeframe"]) for m in updated]
    assert ("USDJPY", "H1") in pairs
    
    # Remove market
    db.remove_monitored_market("USDJPY", "H1")
    after_remove = db.get_monitored_markets()
    after_pairs = [(m["symbol"], m["timeframe"]) for m in after_remove]
    assert ("USDJPY", "H1") not in after_pairs
