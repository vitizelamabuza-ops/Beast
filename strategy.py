"""Trading strategy combining trend, momentum, volatility and confirmation.
Produces signal dictionary with confidence 0-100 and suggested SL/TP distances (in pips or price units).
"""
from typing import Dict, Any
import pandas as pd
import numpy as np
from indicators import compute_all
from config import cfg
import logging

logger = logging.getLogger("strategy")


def score_signal(row: pd.Series, force_buy: bool = False) -> Dict[str, Any]:
    """Return signal type: 'buy', 'sell', or 'hold' with confidence score and reason breakdown.
    
    Args:
        row: Last row of indicator dataframe
        force_buy: If True, force a BUY signal with 99% confidence (for testing)
    """
    # FEATURE 2: FORCE TEST BUTTON
    if force_buy and cfg.ENABLE_FORCE_TEST:
        logger.info("🔴 FORCE TEST ENABLED: Returning 99% confidence BUY signal")
        return {
            "signal": "buy",
            "confidence": 99,
            "reasons": {"trend": 100, "momentum": 100, "volatility": 100, "confirmation": 100},
            "atr": row["atr14"] if not np.isnan(row["atr14"]) else 0.0,
            "stop_distance": float((row["atr14"] * 1.5) if not np.isnan(row["atr14"]) else 0.01),
            "take_distance": float((row["atr14"] * 2.5) if not np.isnan(row["atr14"]) else 0.02),
            "rsi": row["rsi14"],
            "ema50": row["ema50"],
            "ema200": row["ema200"],
        }
    
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

    # Build SL/TP suggestion using ATR multiples
    atr = atr_val
    if atr <= 0 or np.isnan(atr):
        sl = None
        tp = None
    else:
        # We return price distance (not pips) and leave conversion to manager
        sl = float(atr * 1.5)  # 1.5 ATR stop
        tp = float(atr * 2.5)  # 2.5 ATR target

    # FEATURE 1: DEBUG MODE - Log all indicator values
    if cfg.DEBUG_MODE:
        logger.info(
            f"📊 DEBUG: RSI={row['rsi14']:.2f} | EMA50={row['ema50']:.5f} | "
            f"EMA200={row['ema200']:.5f} | Price={row['close']:.5f} | "
            f"Confidence={final_conf}% | Signal={signal.upper()} | "
            f"MACD={row['macd_hist']:.6f} | ADX={row['adx14']:.2f}"
        )

    return {
        "signal": signal,
        "confidence": final_conf,
        "reasons": reasons,
        "atr": atr,
        "stop_distance": sl,
        "take_distance": tp,
        "rsi": row["rsi14"],
        "ema50": row["ema50"],
        "ema200": row["ema200"],
    }


def generate_signal(df: pd.DataFrame, force_buy: bool = False) -> Dict[str, Any]:
    """Compute indicators and return a signal based on the last row.
    
    Args:
        df: Dataframe with price data (open, high, low, close)
        force_buy: If True, force BUY signal (for testing)
    """
    df2 = compute_all(df.tail(300))
    last = df2.iloc[-1]
    return score_signal(last, force_buy=force_buy)
