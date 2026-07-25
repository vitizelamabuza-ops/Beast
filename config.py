"""Configuration loader for MT5 bot.
Loads environment variables from .env and provides typed config values.
"""
from dataclasses import dataclass
from dotenv import load_dotenv
import os

load_dotenv()

@dataclass
class Config:
    MT5_LOGIN: int | None = None
    MT5_PASSWORD: str | None = None
    MT5_SERVER: str | None = None
    MT5_PATH: str | None = None  # optional path to terminal64.exe
    SYMBOL: str = "EURUSD"
    TIMEFRAME: str = "H1"  # e.g., M1, M5, H1, D1
    LOT_SIZE: float = 0.01
    RISK_PERCENT: float = 1.0  # risk percent per trade (1-2)
    CONFIDENCE_THRESHOLD: int = 85
    POLL_INTERVAL: int = 60  # seconds between checks
    MAX_SPREAD_PIPS: float = 3.0
    HIST_PERIODS: int = 500


def _get_int(key: str) -> int | None:
    v = os.getenv(key)
    return int(v) if v and v.isdigit() else None


def _get_float(key: str, default: float) -> float:
    try:
        return float(os.getenv(key, default))
    except Exception:
        return default


cfg = Config(
    MT5_LOGIN=_get_int("MT5_LOGIN"),
    MT5_PASSWORD=os.getenv("MT5_PASSWORD"),
    MT5_SERVER=os.getenv("MT5_SERVER"),
    MT5_PATH=os.getenv("MT5_PATH"),
    SYMBOL=os.getenv("SYMBOL", "EURUSD"),
    TIMEFRAME=os.getenv("TIMEFRAME", "H1"),
    LOT_SIZE=_get_float("LOT_SIZE", 0.01),
    RISK_PERCENT=_get_float("RISK_PERCENT", 1.0),
    CONFIDENCE_THRESHOLD=int(os.getenv("CONFIDENCE_THRESHOLD", "85")),
    POLL_INTERVAL=int(os.getenv("POLL_INTERVAL", "60")),
    MAX_SPREAD_PIPS=_get_float("MAX_SPREAD_PIPS", 3.0),
    HIST_PERIODS=int(os.getenv("HIST_PERIODS", "500")),
)


if __name__ == "__main__":
    print(cfg)
