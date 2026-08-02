from src.engine.classifier import MarketClassifier
from src.engine.db import Database
from src.engine.models import Candle
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
