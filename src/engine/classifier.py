from datetime import datetime
from typing import List, Dict, Any, Tuple
from .models import Candle, MarketClassification, IndicatorSignal, MarketStateResponse
from .indicators import TechnicalIndicators, PriceActionIndicators
from .db import Database

class MarketClassifier:
    def __init__(self, db: Database):
        self.db = db

    def classify(self, candles: List[Candle]) -> MarketStateResponse:
        """
        Classifies the market and calculates overall indicator signals and confidence.
        """
        n = len(candles)
        if n < 50:
            # Fallback for insufficient data
            dummy_candle = candles[-1] if candles else Candle(time=datetime.now(), open=0, high=0, low=0, close=0)
            return MarketStateResponse(
                candle=dummy_candle,
                classification=MarketClassification(
                    trend_state="Insufficient Data",
                    volatility_state="Low",
                    momentum_state="Neutral",
                    primary_regime="Mean Reversion"
                ),
                indicator_signals={},
                confidence_buy=50.0,
                confidence_sell=50.0,
                recommendation="Please feed at least 50 historical candles to run MIE classification.",
                history=candles
            )

        # Get prices
        closes = [c.close for c in candles]
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        
        # 1. Calculate technical values
        ema20 = TechnicalIndicators.calculate_ema(closes, 20)
        ema50 = TechnicalIndicators.calculate_ema(closes, 50)
        ema200 = TechnicalIndicators.calculate_ema(closes, 200)
        
        adx = TechnicalIndicators.calculate_adx(candles, 14)
        rsi = TechnicalIndicators.calculate_rsi(closes, 14)
        atr = TechnicalIndicators.calculate_atr(candles, 14)
        upper, bb_mid, lower = TechnicalIndicators.calculate_bollinger_bands(closes, 20)
        k_vals, d_vals = TechnicalIndicators.calculate_stochastic(candles, 14, 3)
        macd, macd_sig, macd_hist = TechnicalIndicators.calculate_macd(closes, 12, 26, 9)
        
        # Price Action
        pa = PriceActionIndicators.detect_market_structure(candles, 5, 5)
        
        # Get latest values
        last_close = closes[-1]
        last_ema20 = ema20[-1] if ema20 else last_close
        last_ema50 = ema50[-1] if ema50 else last_close
        last_ema200 = ema200[-1] if ema200 else last_close
        last_adx = adx[-1] if adx else 15.0
        last_rsi = rsi[-1] if rsi else 50.0
        last_atr = atr[-1] if atr else 0.0
        
        # 2. Determine Volatility State
        volatility_state = "Medium"
        if len(atr) > 20:
            atr_sma = sum(atr[-20:]) / 20
            if last_atr > 1.2 * atr_sma:
                volatility_state = "High"
            elif last_atr < 0.8 * atr_sma:
                volatility_state = "Low"
                
        # 3. Determine Momentum State
        momentum_state = "Neutral"
        if last_rsi > 60:
            momentum_state = "Bullish"
        elif last_rsi < 40:
            momentum_state = "Bearish"
            
        # 4. Determine Trend State & Primary Regime
        primary_regime = "Mean Reversion"
        if last_adx > 22:
            primary_regime = "Trend Following"
            
        trend_state = "Ranging (Choppy)"
        if primary_regime == "Trend Following":
            if last_ema20 > last_ema50 > last_ema200:
                trend_state = "Strong Uptrend"
            elif last_ema20 < last_ema50 < last_ema200:
                trend_state = "Strong Downtrend"
            elif last_close > last_ema200:
                trend_state = "Weak Uptrend"
            else:
                trend_state = "Weak Downtrend"
        else:
            # Check BB width
            if len(upper) > 0:
                bb_width = (upper[-1] - lower[-1]) / bb_mid[-1]
                if bb_width < 0.01:
                    trend_state = "Ranging (Tight)"
                    
        classification = MarketClassification(
            trend_state=trend_state,
            volatility_state=volatility_state,
            momentum_state=momentum_state,
            primary_regime=primary_regime
        )
        
        # 5. Calculate Individual Indicator Signals
        signals = {}
        
        # EMA crossover signal
        ema_sig = "NEUTRAL"
        if last_ema20 > last_ema50:
            ema_sig = "BUY"
        elif last_ema20 < last_ema50:
            ema_sig = "SELL"
        signals["EMA_Cross"] = IndicatorSignal(name="EMA_Cross", value=last_ema20 - last_ema50, signal=ema_sig, confidence=0.0)
        
        # RSI signal
        rsi_sig = "NEUTRAL"
        if last_rsi < 30:
            rsi_sig = "BUY"
        elif last_rsi > 70:
            rsi_sig = "SELL"
        signals["RSI"] = IndicatorSignal(name="RSI", value=last_rsi, signal=rsi_sig, confidence=0.0)
        
        # MACD Signal
        macd_sig_val = "NEUTRAL"
        if len(macd_hist) > 1:
            if macd_hist[-1] > 0 and macd_hist[-2] <= 0:
                macd_sig_val = "BUY"
            elif macd_hist[-1] < 0 and macd_hist[-2] >= 0:
                macd_sig_val = "SELL"
        signals["MACD"] = IndicatorSignal(name="MACD", value=macd_hist[-1] if macd_hist else 0.0, signal=macd_sig_val, confidence=0.0)
        
        # Stochastic Signal
        stoch_sig = "NEUTRAL"
        if len(k_vals) > 1 and len(d_vals) > 1:
            k_curr, k_prev = k_vals[-1], k_vals[-2]
            d_curr, d_prev = d_vals[-1], d_vals[-2]
            if k_curr < 20 and k_curr > d_curr and k_prev <= d_prev:
                stoch_sig = "BUY"
            elif k_curr > 80 and k_curr < d_curr and k_prev >= d_prev:
                stoch_sig = "SELL"
        signals["Stochastic"] = IndicatorSignal(name="Stochastic", value=k_vals[-1] if k_vals else 50.0, signal=stoch_sig, confidence=0.0)
        
        # Market Structure Signal (BOS)
        bos_sig = "NEUTRAL"
        if pa["bos"] == "BULLISH_BOS":
            bos_sig = "BUY"
        elif pa["bos"] == "BEARISH_BOS":
            bos_sig = "SELL"
        signals["Market_Structure"] = IndicatorSignal(name="Market_Structure", value=0.0, signal=bos_sig, confidence=0.0)
        
        # 6. Apply Dynamic Scoring Weights from Database
        db_scores = self.db.get_indicator_scores()
        
        buy_weight_sum = 0.0
        sell_weight_sum = 0.0
        total_weight = 0.0
        
        for name, sig in signals.items():
            # Get score from DB, default to 50.0 if not yet scored
            score_dict = db_scores.get(name, {})
            score = score_dict.get(primary_regime, 50.0)
            
            # Map confidence weight to 0.0-1.0
            sig.confidence = score / 100.0
            
            if sig.signal != "NEUTRAL":
                total_weight += sig.confidence
                if sig.signal == "BUY":
                    buy_weight_sum += sig.confidence
                elif sig.signal == "SELL":
                    sell_weight_sum += sig.confidence
                    
        # Calculate overall probability
        if total_weight > 0:
            confidence_buy = (buy_weight_sum / total_weight) * 100.0
            confidence_sell = (sell_weight_sum / total_weight) * 100.0
        else:
            confidence_buy = 50.0
            confidence_sell = 50.0
            
        # Determine actionable recommendation
        recommendation = "HOLD / NEUTRAL"
        if confidence_buy > 65:
            recommendation = f"STRONG BUY ({confidence_buy:.1f}% confidence)"
            if primary_regime == "Mean Reversion":
                recommendation += " - Mean Reversion long entry at support."
            else:
                recommendation += " - Trend continuation long breakout."
        elif confidence_sell > 65:
            recommendation = f"STRONG SELL ({confidence_sell:.1f}% confidence)"
            if primary_regime == "Mean Reversion":
                recommendation += " - Mean Reversion short entry at resistance."
            else:
                recommendation += " - Trend continuation short breakout."
        else:
            if primary_regime == "Mean Reversion":
                recommendation = "NEUTRAL - Market in tight range. Wait for breakout or limit orders at boundaries."
            else:
                recommendation = "NEUTRAL - Trend slowing down or indecisive. Avoid entry."
                
        return MarketStateResponse(
            candle=candles[-1],
            classification=classification,
            indicator_signals=signals,
            confidence_buy=confidence_buy,
            confidence_sell=confidence_sell,
            recommendation=recommendation,
            history=candles[-40:]
        )
