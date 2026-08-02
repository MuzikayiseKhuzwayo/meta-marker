from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Dict, Optional

class Candle(BaseModel):
    time: datetime = Field(..., description="Timestamp of the candle close")
    open: float = Field(..., description="Open price")
    high: float = Field(..., description="High price")
    low: float = Field(..., description="Low price")
    close: float = Field(..., description="Close price")
    volume: float = Field(0.0, description="Volume")
    symbol: str = Field("XAUUSD", description="Symbol name")
    timeframe: str = Field("M15", description="Time signature, e.g. M5, M15, H1")

class MarketClassification(BaseModel):
    trend_state: str = Field(..., description="e.g., 'Strong Uptrend', 'Strong Downtrend', 'Ranging (Choppy)', 'Ranging (Tight)'")
    volatility_state: str = Field(..., description="e.g., 'High', 'Medium', 'Low'")
    momentum_state: str = Field(..., description="e.g., 'Bullish', 'Bearish', 'Neutral'")
    primary_regime: str = Field(..., description="e.g., 'Trend Following', 'Mean Reversion'")

class IndicatorSignal(BaseModel):
    name: str
    value: float
    signal: str = Field(..., description="e.g., 'BUY', 'SELL', 'NEUTRAL'")
    confidence: float = Field(..., description="Confidence weight between 0.0 and 1.0")

class MarketStateResponse(BaseModel):
    symbol: str = Field("XAUUSD", description="Symbol name")
    timeframe: str = Field("M15", description="Time signature")
    candle: Candle
    classification: MarketClassification
    indicator_signals: Dict[str, IndicatorSignal]
    confidence_buy: float = Field(..., description="Overall Buy probability 0-100%")
    confidence_sell: float = Field(..., description="Overall Sell probability 0-100%")
    recommendation: str = Field(..., description="Actionable recommendation message")
    history: List[Candle] = Field(default_factory=list, description="Recent candle history for charting")
