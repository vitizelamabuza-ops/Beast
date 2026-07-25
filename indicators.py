"""Indicator helper functions using pandas and ta
"""
from typing import Tuple
import pandas as pd
import numpy as np
import ta


def ensure_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df.rename(columns={
        "time": "time",
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "close",
        "tick_volume": "volume",
    })
    return df


def ema(df: pd.DataFrame, length: int = 50) -> pd.Series:
    return ta.trend.ema_indicator(df["close"], length)


def rsi(df: pd.DataFrame, length: int = 14) -> pd.Series:
    return ta.momentum.rsi(df["close"], length)


def atr(df: pd.DataFrame, length: int = 14) -> pd.Series:
    return ta.volatility.average_true_range(df["high"], df["low"], df["close"], length)


def macd_histogram(df: pd.DataFrame) -> pd.Series:
    macd = ta.trend.MACD(df["close"])  # default 12,26,9
    return macd.macd_diff()


def adx(df: pd.DataFrame, length: int = 14) -> pd.Series:
    return ta.trend.adx(df["high"], df["low"], df["close"], length)


def slope(series: pd.Series, length: int = 5) -> float:
    """Return normalized slope (last window) — approximate momentum direction."""
    if len(series) < length:
        return 0.0
    y = series.values[-length:]
    x = np.arange(len(y))
    # linear regression slope
    A = np.vstack([x, np.ones(len(x))]).T
    m, _ = np.linalg.lstsq(A, y, rcond=None)[0]
    # normalize by price level
    denom = np.mean(np.abs(y)) if np.mean(np.abs(y)) != 0 else 1
    return float(m / denom)


def compute_all(df: pd.DataFrame) -> pd.DataFrame:
    df = ensure_columns(df)
    df = df.copy()
    df["ema50"] = ema(df, 50)
    df["ema200"] = ema(df, 200)
    df["rsi14"] = rsi(df, 14)
    df["atr14"] = atr(df, 14)
    df["macd_hist"] = macd_histogram(df)
    df["adx14"] = adx(df, 14)
    df["ema_slope"] = df["ema50"].rolling(5).apply(lambda x: slope(x, max(3, len(x))), raw=False)
    df["close_slope"] = df["close"].rolling(5).apply(lambda x: slope(x, max(3, len(x))), raw=False)
    return df
