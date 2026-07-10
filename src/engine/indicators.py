import math
from typing import List, Dict, Tuple, Optional
from .models import Candle, IndicatorSignal

class TechnicalIndicators:
    @staticmethod
    def calculate_sma(prices: List[float], period: int) -> List[float]:
        if len(prices) < period:
            return []
        smas = []
        for i in range(len(prices) - period + 1):
            smas.append(sum(prices[i:i+period]) / period)
        return smas

    @staticmethod
    def calculate_ema(prices: List[float], period: int) -> List[float]:
        if len(prices) < period:
            return []
        emas = []
        multiplier = 2 / (period + 1)
        
        # Seed with SMA
        initial_sma = sum(prices[:period]) / period
        emas.append(initial_sma)
        
        for price in prices[period:]:
            next_ema = (price - emas[-1]) * multiplier + emas[-1]
            emas.append(next_ema)
        return emas

    @staticmethod
    def calculate_rsi(prices: List[float], period: int = 14) -> List[float]:
        if len(prices) <= period:
            return []
        
        gains = []
        losses = []
        
        for i in range(1, len(prices)):
            diff = prices[i] - prices[i-1]
            gains.append(diff if diff > 0 else 0.0)
            losses.append(-diff if diff < 0 else 0.0)
            
        # Initial averages
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period
        
        rsi_values = []
        if avg_loss == 0:
            rsi_values.append(100.0)
        else:
            rs = avg_gain / avg_loss
            rsi_values.append(100.0 - (100.0 / (1.0 + rs)))
            
        for i in range(period, len(gains)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
            
            if avg_loss == 0:
                rsi_values.append(100.0)
            else:
                rs = avg_gain / avg_loss
                rsi_values.append(100.0 - (100.0 / (1.0 + rs)))
                
        return rsi_values

    @staticmethod
    def calculate_macd(prices: List[float], fast_period: int = 12, slow_period: int = 26, signal_period: int = 9) -> Tuple[List[float], List[float], List[float]]:
        # Need enough data
        if len(prices) < slow_period + signal_period:
            return [], [], []
            
        fast_emas = TechnicalIndicators.calculate_ema(prices, fast_period)
        slow_emas = TechnicalIndicators.calculate_ema(prices, slow_period)
        
        # Align lengths
        offset = slow_period - fast_period
        macd_line = []
        for i in range(len(slow_emas)):
            macd_line.append(fast_emas[i + offset] - slow_emas[i])
            
        signal_line = TechnicalIndicators.calculate_ema(macd_line, signal_period)
        
        # Align lengths
        macd_offset = len(macd_line) - len(signal_line)
        aligned_macd = macd_line[macd_offset:]
        histogram = [m - s for m, s in zip(aligned_macd, signal_line)]
        
        return aligned_macd, signal_line, histogram

    @staticmethod
    def calculate_atr(candles: List[Candle], period: int = 14) -> List[float]:
        if len(candles) <= period:
            return []
            
        true_ranges = []
        for i in range(1, len(candles)):
            h = candles[i].high
            l = candles[i].low
            prev_c = candles[i-1].close
            tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
            true_ranges.append(tr)
            
        # Wilder's smoothing for ATR
        atrs = []
        current_atr = sum(true_ranges[:period]) / period
        atrs.append(current_atr)
        
        for tr in true_ranges[period:]:
            current_atr = (current_atr * (period - 1) + tr) / period
            atrs.append(current_atr)
            
        return atrs

    @staticmethod
    def calculate_bollinger_bands(prices: List[float], period: int = 20, num_std: float = 2.0) -> Tuple[List[float], List[float], List[float]]:
        if len(prices) < period:
            return [], [], []
            
        smas = TechnicalIndicators.calculate_sma(prices, period)
        upper_band = []
        lower_band = []
        
        for i in range(len(smas)):
            sub_prices = prices[i : i + period]
            mean = smas[i]
            variance = sum((p - mean) ** 2 for p in sub_prices) / period
            std_dev = math.sqrt(variance)
            upper_band.append(mean + num_std * std_dev)
            lower_band.append(mean - num_std * std_dev)
            
        return upper_band, smas, lower_band

    @staticmethod
    def calculate_stochastic(candles: List[Candle], k_period: int = 14, d_period: int = 3) -> Tuple[List[float], List[float]]:
        if len(candles) < k_period + d_period:
            return [], []
            
        k_values = []
        for i in range(k_period - 1, len(candles)):
            sub_candles = candles[i - k_period + 1 : i + 1]
            close = candles[i].close
            lowest_low = min(c.low for c in sub_candles)
            highest_high = max(c.high for c in sub_candles)
            
            denom = highest_high - lowest_low
            if denom == 0:
                k_values.append(50.0)
            else:
                k_values.append(((close - lowest_low) / denom) * 100.0)
                
        # D is SMA of K
        d_values = TechnicalIndicators.calculate_sma(k_values, d_period)
        aligned_k = k_values[d_period - 1:]
        
        return aligned_k, d_values

    @staticmethod
    def calculate_adx(candles: List[Candle], period: int = 14) -> List[float]:
        if len(candles) < 2 * period:
            return []
            
        plus_dm = []
        minus_dm = []
        tr_list = []
        
        for i in range(1, len(candles)):
            h_diff = candles[i].high - candles[i-1].high
            l_diff = candles[i-1].low - candles[i].low
            
            p_dm = h_diff if h_diff > l_diff and h_diff > 0 else 0.0
            m_dm = l_diff if l_diff > h_diff and l_diff > 0 else 0.0
            
            plus_dm.append(p_dm)
            minus_dm.append(m_dm)
            
            h = candles[i].high
            l = candles[i].low
            prev_c = candles[i-1].close
            tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
            tr_list.append(tr)
            
        # Wilder's Smoothing
        smoothed_tr = sum(tr_list[:period])
        smoothed_plus_dm = sum(plus_dm[:period])
        smoothed_minus_dm = sum(minus_dm[:period])
        
        plus_di = [100.0 * (smoothed_plus_dm / smoothed_tr) if smoothed_tr else 0.0]
        minus_di = [100.0 * (smoothed_minus_dm / smoothed_tr) if smoothed_tr else 0.0]
        
        dx_list = []
        denom = plus_di[-1] + minus_di[-1]
        dx = 100.0 * abs(plus_di[-1] - minus_di[-1]) / denom if denom else 0.0
        dx_list.append(dx)
        
        for i in range(period, len(tr_list)):
            smoothed_tr = smoothed_tr - (smoothed_tr / period) + tr_list[i]
            smoothed_plus_dm = smoothed_plus_dm - (smoothed_plus_dm / period) + plus_dm[i]
            smoothed_minus_dm = smoothed_minus_dm - (smoothed_minus_dm / period) + minus_dm[i]
            
            p_di = 100.0 * (smoothed_plus_dm / smoothed_tr) if smoothed_tr else 0.0
            m_di = 100.0 * (smoothed_minus_dm / smoothed_tr) if smoothed_tr else 0.0
            plus_di.append(p_di)
            minus_di.append(m_di)
            
            denom = p_di + m_di
            dx = 100.0 * abs(p_di - m_di) / denom if denom else 0.0
            dx_list.append(dx)
            
        # ADX is SMA/Wilder of DX
        adx_values = []
        current_adx = sum(dx_list[:period]) / period
        adx_values.append(current_adx)
        
        for dx_val in dx_list[period:]:
            current_adx = (current_adx * (period - 1) + dx_val) / period
            adx_values.append(current_adx)
            
        return adx_values


class PriceActionIndicators:
    @staticmethod
    def identify_swings(candles: List[Candle], left_bars: int = 5, right_bars: int = 5) -> Tuple[List[Dict], List[Dict]]:
        """
        Identify swing highs and swing lows.
        A Swing High requires the high of the candle to be greater than all high prices
        of left_bars candles before it and right_bars candles after it.
        """
        swing_highs = []
        swing_lows = []
        
        n = len(candles)
        for i in range(left_bars, n - right_bars):
            val_high = candles[i].high
            val_low = candles[i].low
            
            is_high = True
            is_low = True
            
            # Check left and right bounds
            for offset in range(-left_bars, right_bars + 1):
                if offset == 0:
                    continue
                neighbor = candles[i + offset]
                if neighbor.high >= val_high:
                    is_high = False
                if neighbor.low <= val_low:
                    is_low = False
                    
            if is_high:
                swing_highs.append({"index": i, "price": val_high, "time": candles[i].time})
            if is_low:
                swing_lows.append({"index": i, "price": val_low, "time": candles[i].time})
                
        return swing_highs, swing_lows

    @staticmethod
    def detect_market_structure(candles: List[Candle], left_bars: int = 5, right_bars: int = 5) -> Dict:
        """
        Detect Swing Highs, Swing Lows, BOS, and CHoCH.
        """
        swing_highs, swing_lows = PriceActionIndicators.identify_swings(candles, left_bars, right_bars)
        
        bos_events = []
        choch_events = []
        
        last_high = swing_highs[-1] if swing_highs else None
        last_low = swing_lows[-1] if swing_lows else None
        
        # Simple S/R levels based on recent swings
        resistance_levels = [sh["price"] for sh in swing_highs[-3:]] if swing_highs else []
        support_levels = [sl["price"] for sl in swing_lows[-3:]] if swing_lows else []
        
        # Check last close to determine breakouts
        last_close = candles[-1].close if candles else 0.0
        
        bos_signal = "NEUTRAL"
        if last_high and last_close > last_high["price"]:
            bos_signal = "BULLISH_BOS"
        elif last_low and last_close < last_low["price"]:
            bos_signal = "BEARISH_BOS"
            
        # Identify Order Blocks (OB)
        # Bullish OB: Last down candle before strong up move breaking structure
        # Bearish OB: Last up candle before strong down move breaking structure
        order_blocks = []
        
        # Search backwards to find order blocks
        if len(candles) > 10:
            for i in range(len(candles) - 10, len(candles) - 1):
                c = candles[i]
                c_next = candles[i+1]
                # Strong body move
                body = abs(c_next.close - c_next.open)
                avg_atr = (c_next.high - c_next.low)
                if body > avg_atr * 0.7:  # strong impulse candle
                    if c_next.close > c_next.open and c.close < c.open:
                        order_blocks.append({"type": "BULLISH_OB", "price": c.low, "time": c.time})
                    elif c_next.close < c_next.open and c.close > c.open:
                        order_blocks.append({"type": "BEARISH_OB", "price": c.high, "time": c.time})
                        
        return {
            "swing_highs": swing_highs,
            "swing_lows": swing_lows,
            "support": support_levels,
            "resistance": resistance_levels,
            "bos": bos_signal,
            "order_blocks": order_blocks[-3:] if order_blocks else []
        }
