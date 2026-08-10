"""Configuration loader for MT5 bot.
Loads environment variables from .env and provides typed config values.
"""
from dataclasses import dataclass
from dotenv import load_dotenv
import os

load_dotenv()

@dataclass
class Config:
    MT5_TERMINAL_PATH: str | None = None  # preferred full path to terminal64.exe
    MT5_LOGIN: int | None = None
    MT5_PASSWORD: str | None = None
    MT5_SERVER: str | None = None
    MT5_PATH: str | None = None  # legacy optional path to terminal64.exe
    SYMBOL: str = "EURUSD"
    TIMEFRAME: str = "H1"  # e.g., M1, M5, H1, D1
    LOT_SIZE: float = 0.01
    RISK_PERCENT: float = 1.0  # risk percent per trade (1-2)
    CONFIDENCE_THRESHOLD: int = 85
    MIN_CONFIDENCE_TO_TRADE: int = 40  # NEW: Lower this for testing (was 85)
    POLL_INTERVAL: int = 60  # seconds between checks
    MAX_SPREAD_PIPS: float = 3.0
    HIST_PERIODS: int = 500
    DEBUG_MODE: bool = False  # NEW: Print debug info every tick
    ENABLE_FORCE_TEST: bool = False  # NEW: Force a BUY signal for testing
    ENABLE_VISUAL_ARROWS: bool = True  # NEW: Draw arrows on chart
    ENABLE_DASHBOARD: bool = True  # NEW: Show live dashboard on chart
    MAX_TRADES_PER_DAY: int = 3  # NEW: Max trades in 24 hours


def _get_int(key: str) -> int | None:
    v = os.getenv(key)
    return int(v) if v and v.isdigit() else None


def _get_float(key: str, default: float) -> float:
    try:
        return float(os.getenv(key, default))
    except Exception:
        return default


def _get_bool(key: str, default: bool) -> bool:
    v = os.getenv(key, str(default)).lower()
    return v in ("true", "1", "yes")


cfg = Config(
    MT5_TERMINAL_PATH=os.getenv("MT5_TERMINAL_PATH"),
    MT5_LOGIN=_get_int("MT5_LOGIN"),
    MT5_PASSWORD=os.getenv("MT5_PASSWORD"),
    MT5_SERVER=os.getenv("MT5_SERVER"),
    MT5_PATH=os.getenv("MT5_PATH"),
    SYMBOL=os.getenv("SYMBOL", "EURUSD"),
    TIMEFRAME=os.getenv("TIMEFRAME", "H1"),
    LOT_SIZE=_get_float("LOT_SIZE", 0.01),
    RISK_PERCENT=_get_float("RISK_PERCENT", 1.0),
    CONFIDENCE_THRESHOLD=int(os.getenv("CONFIDENCE_THRESHOLD", "85")),
    MIN_CONFIDENCE_TO_TRADE=int(os.getenv("MIN_CONFIDENCE_TO_TRADE", "40")),
    POLL_INTERVAL=int(os.getenv("POLL_INTERVAL", "60")),
    MAX_SPREAD_PIPS=_get_float("MAX_SPREAD_PIPS", 3.0),
    HIST_PERIODS=int(os.getenv("HIST_PERIODS", "500")),
    DEBUG_MODE=_get_bool("DEBUG_MODE", False),
    ENABLE_FORCE_TEST=_get_bool("ENABLE_FORCE_TEST", False),
    ENABLE_VISUAL_ARROWS=_get_bool("ENABLE_VISUAL_ARROWS", True),
    ENABLE_DASHBOARD=_get_bool("ENABLE_DASHBOARD", True),
    MAX_TRADES_PER_DAY=int(os.getenv("MAX_TRADES_PER_DAY", "3")),
)


if __name__ == "__main__":
    print(cfg)
