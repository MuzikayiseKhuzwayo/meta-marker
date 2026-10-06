# How-To Guide: Custom Indicator Integration

This guide walks through adding a new technical indicator or algorithmic signal to Meta-Marker's deterministic classification matrix and dynamic scoring engine.

---

## 1. Overview of the Pipeline

Adding an indicator requires three simple steps:
1. **Define Math in [`src/engine/indicators.py`](file:///c:/Users/muzik/Documents/GitHub/meta-marker/src/engine/indicators.py)**: Pure function accepting candle data and returning numerical values.
2. **Compute Signal in [`src/engine/classifier.py`](file:///c:/Users/muzik/Documents/GitHub/meta-marker/src/engine/classifier.py)**: Translate the value into `BUY`, `SELL`, or `NEUTRAL` and package it as an `IndicatorSignal`.
3. **Automatic Evaluation in [`src/engine/scorer.py`](file:///c:/Users/muzik/Documents/GitHub/meta-marker/src/engine/scorer.py)**: The scoring engine automatically tracks prediction outcomes against subsequent candle closes and updates SQLite reliability weights without manual wiring!

---

## 2. Step 1: Implement Indicator Function

Open [`src/engine/indicators.py`](file:///c:/Users/muzik/Documents/GitHub/meta-marker/src/engine/indicators.py) and add your indicator method to `TechnicalIndicators`:

```python
@staticmethod
def calculate_cci(candles: List[Candle], period: int = 20) -> List[float]:
    """
    Commodity Channel Index (CCI).
    """
    if len(candles) < period:
        return []
    
    tp_list = [(c.high + c.low + c.close) / 3.0 for c in candles]
    cci_values = []
    
    for i in range(period - 1, len(tp_list)):
        window = tp_list[i - period + 1 : i + 1]
        sma = sum(window) / period
        mean_dev = sum(abs(x - sma) for x in window) / period
        if mean_dev == 0:
            cci = 0.0
        else:
            cci = (tp_list[i] - sma) / (0.015 * mean_dev)
        cci_values.append(cci)
        
    return cci_values
```

---

## 3. Step 2: Register in Market Classifier

Open [`src/engine/classifier.py`](file:///c:/Users/muzik/Documents/GitHub/meta-marker/src/engine/classifier.py):

1. Call your function during `classify(candles)`:
   ```python
   cci_vals = TechnicalIndicators.calculate_cci(candles, 20)
   last_cci = cci_vals[-1] if cci_vals else 0.0
   ```
2. Derive the signal:
   ```python
   cci_sig = "NEUTRAL"
   if last_cci < -100:
       cci_sig = "BUY"
   elif last_cci > 100:
       cci_sig = "SELL"
   signals["CCI"] = IndicatorSignal(name="CCI", value=last_cci, signal=cci_sig, confidence=0.0)
   ```

---

## 4. Step 3: Run Tests & Verify Dynamic Scoring

1. Add a test in `tests/test_indicators.py` verifying the mathematical accuracy.
2. Run `uv run pytest`.
3. Boot the engine or run `uv run meta-marker classify`.
4. Your new indicator will now automatically appear in the **Indicator Matrix**, receive dynamic reliability updates in SQLite, and contribute to the **Confidence Engine** weighted dial!
