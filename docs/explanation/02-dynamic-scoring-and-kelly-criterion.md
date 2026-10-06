# Explanation: Dynamic Reliability Scoring & Kelly Criterion

This document details the mathematical formulation of Meta-Marker's dynamic indicator scoring and optimal risk allocation engine.

---

## 1. Dynamic Reliability Scoring

Rather than trusting an indicator based on backtested assumptions, Meta-Marker audits indicator performance continuously on live closed bars:

$$\text{Score}_{i, r} = \left(\frac{N_{\text{correct}}}{N_{\text{total}}}\right)_{i, r} \times 100$$

Where:
- $i$ is the specific indicator (e.g. `EMA_Cross`, `RSI`, `MACD`, `Stochastic`, `Market_Structure`).
- $r$ is the active market regime (e.g. `Trend Following` vs. `Mean Reversion`).

### Consensus Weighting
When generating overall directional probability:
$$\text{Weight}_i = \frac{\text{Score}_{i, r}}{100}$$

$$\text{Confidence}_{\text{Buy}} = \frac{\sum_{i \in \text{BUY}} \text{Weight}_i}{\sum \text{Weight}_{\text{active}}} \times 100$$

$$\text{Confidence}_{\text{Sell}} = \frac{\sum_{i \in \text{SELL}} \text{Weight}_i}{\sum \text{Weight}_{\text{active}}} \times 100$$

If an indicator exhibits a 30% win-rate during choppy consolidations, its contribution to trade recommendations is automatically compressed without manual intervention.

---

## 2. Kelly Criterion & Half-Kelly Position Sizing

When confidence exceeds the 65% decision threshold, Meta-Marker calculates mathematical position sizing using the **Kelly Criterion**:

$$f^* = \frac{p \cdot b - q}{b} = p - \frac{1 - p}{b}$$

Where:
- $p$ is the estimated probability of a winning trade ($\frac{\text{Confidence}}{100}$).
- $q = 1 - p$ is the probability of a losing trade.
- $b$ is the reward-to-risk ratio (standardized to $b = 2.0$ based on our 2:1 Take Profit / Stop Loss geometry).

### Half-Kelly Safety Factor
Full-Kelly sizing maximizes long-term capital growth but results in severe drawdown volatility. In institutional risk management, **Half-Kelly** is universally preferred:

$$f_{\text{half}} = \frac{f^*}{2}$$

### Risk Caps
To ensure institutional safety, the calculated allocation is bounded:
$$0.0\% \le \text{Risk Sizing} \le 5.0\%$$

This guarantees that even during exceptional setup alignments, portfolio exposure never exceeds a disciplined 5% maximum threshold.
