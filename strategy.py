"""Trading strategy combining trend, momentum, volatility and confirmation.
Produces signal dictionary with confidence 0-100 and suggested SL/TP distances (in pips or price units).
"""
from typing import Dict, Any
import pandas as pd
import numpy as np
from indicators import compute_all


def score_signal(row: pd.Series) -> Dict[str, Any]:
    """Return signal type: 'buy', 'sell', or 'hold' with confidence score and reason breakdown."""
    # weights for different checks
    weights = {
        "trend": 0.35,
        "momentum": 0.25,
        "volatility": 0.20,
        "confirmation": 0.20,
    }

    score = 0.0
    reasons = {}

    # Trend via EMA50 vs EMA200
    if row["ema50"] > row["ema200"]:
        trend_dir = "bull"
        score += 100 * weights["trend"]
        reasons["trend"] = 100
    else:
        trend_dir = "bear"
        reasons["trend"] = 0

    # Momentum via MACD histogram and RSI
    macd_ok = row["macd_hist"] > 0
    rsi_ok = row["rsi14"] > 50
    momentum_score = ((1.0 if macd_ok else 0.0) + (1.0 if rsi_ok else 0.0)) / 2.0 * 100
    score += momentum_score * weights["momentum"]
    reasons["momentum"] = momentum_score

    # Volatility via ATR — require ATR not too small
    atr_val = row["atr14"] if not np.isnan(row["atr14"]) else 0.0
    # normalize atr against price
    vol_score = min(100, (atr_val / max(1e-6, row["close"])) * 10000)
    score += vol_score * weights["volatility"]
    reasons["volatility"] = vol_score

    # Confirmation: ADX strong trend and slope
    adx_ok = row["adx14"] > 20
    slope_ok = row["ema_slope"] > 0.0 if trend_dir == "bull" else row["ema_slope"] < 0.0
    conf_score = ((1.0 if adx_ok else 0.0) + (1.0 if slope_ok else 0.0)) / 2.0 * 100
    score += conf_score * weights["confirmation"]
    reasons["confirmation"] = conf_score

    final_conf = int(round(score))

    # Determine signal
    signal = "hold"
    if trend_dir == "bull" and macd_ok and rsi_ok and final_conf >= 0:
        # potential buy
        signal = "buy"
    elif trend_dir == "bear" and not macd_ok and not rsi_ok and final_conf >= 0:
        signal = "sell"

    # But we'll only allow trade if confidence >= threshold at higher level

    # Build SL/TP suggestion using ATR multiples
    atr = atr_val
    if atr <= 0 or np.isnan(atr):
        sl = None
        tp = None
    else:
        # We return price distance (not pips) and leave conversion to manager
        sl = float(atr * 1.5)  # 1.5 ATR stop
        tp = float(atr * 2.5)  # 2.5 ATR target

    return {
        "signal": signal,
        "confidence": final_conf,
        "reasons": reasons,
        "atr": atr,
        "stop_distance": sl,
        "take_distance": tp,
    }


def generate_signal(df: pd.DataFrame) -> Dict[str, Any]:
    """Compute indicators and return a signal based on the last row."""
    df2 = compute_all(df.tail(300))
    last = df2.iloc[-1]
    return score_signal(last)
