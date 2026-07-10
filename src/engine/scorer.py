from typing import List, Dict, Any
from .models import Candle, IndicatorSignal
from .db import Database

class IndicatorScorer:
    def __init__(self, db: Database):
        self.db = db

    def evaluate_and_update(self, candles: List[Candle], current_signals: Dict[str, IndicatorSignal], regime: str):
        """
        Evaluate the signals that were generated at the PREVIOUS candle, 
        using the LATEST completed candle that just arrived.
        Update the database scores accordingly.
        """
        if len(candles) < 2:
            return
            
        latest_candle = candles[-1]
        previous_candle = candles[-2]
        
        # Did price go up or down?
        price_moved_up = latest_candle.close > previous_candle.close
        price_moved_down = latest_candle.close < previous_candle.close
        
        # Evaluate signals generated AT the previous candle
        for ind_name, signal in current_signals.items():
            if signal.signal == "NEUTRAL":
                continue
                
            is_correct = False
            if signal.signal == "BUY" and price_moved_up:
                is_correct = True
            elif signal.signal == "SELL" and price_moved_down:
                is_correct = True
                
            # Update score in database for the active market regime
            self.db.update_indicator_score(ind_name, regime, is_correct)
