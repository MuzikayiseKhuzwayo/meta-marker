from src.engine.indicators import TechnicalIndicators
from src.engine.models import Candle
from datetime import datetime

def test_sma():
    prices = [1.0, 2.0, 3.0, 4.0, 5.0]
    smas = TechnicalIndicators.calculate_sma(prices, 3)
    assert len(smas) == 3
    assert smas[0] == 2.0  # (1+2+3)/3
    assert smas[1] == 3.0  # (2+3+4)/3
    assert smas[2] == 4.0  # (3+4+5)/3

def test_ema():
    prices = [1.0, 2.0, 3.0, 4.0, 5.0]
    # EMA 3: multiplier = 2/(3+1) = 0.5
    # Seed (SMA) = (1+2+3)/3 = 2.0
    # Next EMA = (4 - 2.0)*0.5 + 2.0 = 3.0
    # Next EMA = (5 - 3.0)*0.5 + 3.0 = 4.0
    emas = TechnicalIndicators.calculate_ema(prices, 3)
    assert len(emas) == 3
    assert emas[0] == 2.0
    assert emas[1] == 3.0
    assert emas[2] == 4.0

def test_rsi():
    # Simple price movement up
    prices = [10.0] * 16
    for i in range(1, 16):
        prices[i] = prices[i-1] + 1.0  # constant gain
    rsi_vals = TechnicalIndicators.calculate_rsi(prices, 14)
    assert len(rsi_vals) == 2
    assert rsi_vals[0] == 100.0  # All gains, no losses

def test_atr():
    # Create some mock candles with 1.0 true range
    candles = []
    base_time = datetime.now()
    for i in range(20):
        candles.append(Candle(
            time=base_time,
            open=10.0,
            high=11.0,
            low=10.0,
            close=10.5,
            volume=100.0
        ))
    atrs = TechnicalIndicators.calculate_atr(candles, 14)
    assert len(atrs) == 6
    # True range should be constant (high 11.0 - low 10.0) = 1.0
    # True range of first = high 11.0 - low 10.0 = 1.0
    assert abs(atrs[-1] - 1.0) < 0.001
