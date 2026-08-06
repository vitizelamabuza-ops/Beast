"""Logging configuration
"""
import logging
import sys
from logging.handlers import RotatingFileHandler

LOG_FILE = "bot.log"


def setup_logging(level: int = logging.INFO) -> None:
    """Setup logging with file and console handlers.
    
    FEATURE 1: Enhanced logging with timestamps and debug info
    """
    fmt = "%(asctime)s %(levelname)-8s [%(name)s] %(message)s"
    root = logging.getLogger()
    root.setLevel(level)

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(level)
    ch.setFormatter(logging.Formatter(fmt))
    root.addHandler(ch)

    fh = RotatingFileHandler(LOG_FILE, maxBytes=10_000_000, backupCount=3)
    fh.setLevel(level)
    fh.setFormatter(logging.Formatter(fmt))
    root.addHandler(fh)


if __name__ == "__main__":
    setup_logging()
    logging.getLogger("test").info("Logging setup complete")
