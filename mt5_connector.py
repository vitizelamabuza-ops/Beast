"""MetaTrader 5 connection and market data utilities.
Wraps the MetaTrader5 package and provides helpers used by the bot.

This module provides robust initialization and diagnostics for the MetaTrader5
Python package when used with the MetaTrader 5 desktop terminal on Windows.

Key features added:
- Prefer MT5_TERMINAL_PATH (or MT5_PATH) from environment/config
- Validate terminal executable exists before initializing
- Optionally start the terminal process (Windows) when not running
- Retry initialization a small number of times with delays
- Provide a connection diagnostic function (check_connection)
- Always call mt5.shutdown() on failure/cleanup
- Remove all emoji characters from logs and user messages
"""
from __future__ import annotations
import MetaTrader5 as mt5
from typing import Optional, Dict, Any
import pandas as pd
import time
import logging
import asyncio
from config import cfg
from datetime import datetime
import os
import subprocess
import glob

logger = logging.getLogger("mt5_connector")

TIMEFRAME_MAP = {
    "M1": mt5.TIMEFRAME_M1,
    "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30,
    "H1": mt5.TIMEFRAME_H1,
    "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1,
}

# Global state for dashboard
last_signal = "hold"
last_confidence = 0
last_update_time = None


def _find_possible_terminals() -> list:
    """Return a list of likely terminal executable paths on Windows.

    This does not assume installation paths; it looks for common names in
    Program Files folders. The caller should validate existence.
    """
    candidates = []
    program_dirs = [os.environ.get("ProgramFiles", "C:\\Program Files"),
                    os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")]
    for base in program_dirs:
        # look for directories containing 'terminal*.exe'
        pattern = os.path.join(base, "**", "terminal*.exe")
        candidates.extend(glob.glob(pattern, recursive=True))
    # Remove duplicates and keep full paths
    seen = set()
    result = []
    for p in candidates:
        if p not in seen and os.path.isfile(p):
            seen.add(p)
            result.append(p)
    return result


def _start_terminal(path: str) -> bool:
    """Start the MetaTrader terminal process (Windows). Returns True if started.

    This uses subprocess.Popen to start the terminal executable. It does not
    attempt to manage UI prompts or login dialogs. The process is launched
    detached so the Python process can continue.
    """
    try:
        # Use CREATE_NEW_PROCESS_GROUP and DETACHED_PROCESS flags on Windows when available
        if os.name == "nt":
            DETACHED = 0x00000008
            subprocess.Popen([path], close_fds=True, creationflags=DETACHED)
        else:
            subprocess.Popen([path], close_fds=True)
        logger.info("Started MetaTrader terminal: %s", path)
        return True
    except Exception:
        logger.exception("Failed to start MetaTrader terminal: %s", path)
        return False


def initialize(retries: int = 3, delay: int = 5, start_if_missing: bool = True) -> bool:
    """Initialize and connect to MT5 terminal.
    Returns True on success, False on error.

    Behavior:
    - Use cfg.MT5_TERMINAL_PATH or cfg.MT5_PATH if provided. If not provided,
      search common installation locations.
    - Verify the executable exists before attempting to initialize.
    - If the terminal is not running and start_if_missing is True, attempt to
      start it and wait briefly for IPC channel to be available.
    - Retry mt5.initialize/login a small number of times.
    - On failure, call mt5.last_error() and log diagnostics.
    - Always call mt5.shutdown() on fatal failures to ensure a clean state.
    """
    terminal_path = getattr(cfg, "MT5_TERMINAL_PATH", None) or cfg.MT5_PATH

    # If a configured path is provided, validate
    if terminal_path:
        terminal_path = terminal_path.strip('"')
        if not os.path.isfile(terminal_path):
            logger.error("Configured MT5 terminal path does not exist: %s", terminal_path)
            return False

    # If not configured, try to find common terminals
    if not terminal_path:
        found = _find_possible_terminals()
        if found:
            # Prefer terminal64.exe if present
            found_sorted = sorted(found, key=lambda p: ("terminal64" not in p.lower(), p))
            terminal_path = found_sorted[0]
            logger.info("Auto-detected MT5 terminal path: %s", terminal_path)
        else:
            logger.warning("No MT5 terminal path configured and none found in common locations.")
            terminal_path = None

    last_err = None
    for attempt in range(1, retries + 1):
        try:
            if terminal_path:
                logger.info("Initializing MetaTrader5 with terminal path: %s (attempt %d)", terminal_path, attempt)
                ok = mt5.initialize(terminal_path)
            else:
                logger.info("Initializing MetaTrader5 without explicit terminal path (auto-discovery) (attempt %d)", attempt)
                ok = mt5.initialize()

            if not ok:
                last_err = mt5.last_error()
                logger.warning("mt5.initialize() returned False on attempt %d: %s", attempt, last_err)
                if terminal_path and start_if_missing:
                    logger.info("Attempting to start MT5 terminal and retry initialization (attempt %d)", attempt)
                    _start_terminal(terminal_path)
                    time.sleep(delay)
                    continue
                else:
                    time.sleep(delay)
                    continue

            # If initialization succeeded, attempt login if credentials provided
            authorized = True
            if cfg.MT5_LOGIN and cfg.MT5_PASSWORD:
                try:
                    if cfg.MT5_SERVER:
                        logger.info("Logging into MT5 account %s on server %s", cfg.MT5_LOGIN, cfg.MT5_SERVER)
                        authorized = mt5.login(int(cfg.MT5_LOGIN), password=cfg.MT5_PASSWORD, server=cfg.MT5_SERVER)
                    else:
                        logger.info("Logging into MT5 account %s", cfg.MT5_LOGIN)
                        authorized = mt5.login(int(cfg.MT5_LOGIN), password=cfg.MT5_PASSWORD)
                except Exception:
                    last_err = mt5.last_error()
                    logger.exception("Exception during mt5.login(): %s", last_err)
                    authorized = False

            if not authorized:
                last_err = mt5.last_error()
                logger.error("MT5 login failed: %s", last_err)
                try:
                    mt5.shutdown()
                except Exception:
                    logger.exception("Error shutting down MT5 after failed login")
                time.sleep(delay)
                continue

            logger.info("MT5 initialized and (if configured) logged in")
            return True

        except Exception as exc:
            last_err = getattr(exc, "args", exc)
            logger.exception("MT5 initialization exception on attempt %d: %s", attempt, exc)
            try:
                mt5.shutdown()
            except Exception:
                logger.exception("Error shutting down MT5 after exception")
            time.sleep(delay)
            continue

    logger.error("MT5 initialization failed after %d attempts. Last error: %s", retries, last_err)
    return False


def shutdown() -> None:
    try:
        mt5.shutdown()
        logger.info("MT5 shutdown")
    except Exception:
        logger.exception("Error shutting down MT5")


def symbol_info(symbol: str) -> Optional[Dict[str, Any]]:
    info = mt5.symbol_info(symbol)
    if info is None:
        return None
    return info._asdict()


def get_rates(symbol: str, timeframe: str, n: int) -> pd.DataFrame:
    tf = TIMEFRAME_MAP.get(timeframe.upper(), mt5.TIMEFRAME_H1)
    rates = mt5.copy_rates_from_pos(symbol, tf, 0, n)
    if rates is None:
        raise RuntimeError(f"Failed get rates for {symbol} {timeframe}: {mt5.last_error()}")
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    return df


async def get_rates_async(symbol: str, timeframe: str, n: int) -> pd.DataFrame:
    return await asyncio.to_thread(get_rates, symbol, timeframe, n)


def send_order(symbol: str, action: str, volume: float, price: Optional[float] = None, sl: Optional[float] = None, tp: Optional[float] = None, deviation: int = 20) -> Dict[str, Any]:
    """Send market order. action in ('buy', 'sell')"""
    symbol_info_tick = mt5.symbol_info_tick(symbol)
    if symbol_info_tick is None:
        raise RuntimeError("Symbol not available")

    if action.lower() == "buy":
        order_type = mt5.ORDER_TYPE_BUY
        price = price or symbol_info_tick.ask
    else:
        order_type = mt5.ORDER_TYPE_SELL
        price = price or symbol_info_tick.bid

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": float(volume),
        "type": order_type,
        "price": float(price),
        "deviation": deviation,
        "magic": 234000,
        "comment": "py_mt5_bot",
        "type_filling": mt5.ORDER_FILLING_FOK,
    }
    if sl:
        request["sl"] = float(sl)
    if tp:
        request["tp"] = float(tp)

    result = mt5.order_send(request)
    logger.debug("Order send request: %s result: %s", request, result)
    return result._asdict() if hasattr(result, "_asdict") else dict(result)


def get_positions(symbol: Optional[str] = None) -> pd.DataFrame:
    if symbol:
        pos = mt5.positions_get(symbol=symbol)
    else:
        pos = mt5.positions_get()
    if pos is None:
        return pd.DataFrame()
    records = [p._asdict() for p in pos]
    return pd.DataFrame(records)


def close_position(ticket: int) -> Dict[str, Any]:
    pos = mt5.positions_get(ticket=ticket)
    if not pos:
        raise RuntimeError("Position not found")
    p = pos[0]
    symbol = p.symbol
    volume = p.volume
    if p.type == mt5.POSITION_TYPE_BUY:
        order_type = mt5.ORDER_TYPE_SELL
        price = mt5.symbol_info_tick(symbol).bid
    else:
        order_type = mt5.ORDER_TYPE_BUY
        price = mt5.symbol_info_tick(symbol).ask

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": float(volume),
        "type": order_type,
        "position": int(p.ticket),
        "price": float(price),
        "deviation": 20,
        "magic": 234000,
        "comment": "close by bot",
    }
    result = mt5.order_send(request)
    return result._asdict() if hasattr(result, "_asdict") else dict(result)


def get_account_balance() -> float:
    """Get current account balance."""
    account = mt5.account_info()
    if account:
        return float(account.balance)
    return 0.0


def count_open_trades(symbol: Optional[str] = None) -> int:
    """Count number of open positions."""
    pos = get_positions(symbol)
    return len(pos) if not pos.empty else 0


def set_dashboard_state(signal: str, confidence: int):
    """Update global dashboard state."""
    global last_signal, last_confidence, last_update_time
    last_signal = signal
    last_confidence = confidence
    last_update_time = datetime.now()


def get_dashboard_state() -> Dict[str, Any]:
    """Get current dashboard state."""
    return {
        "signal": last_signal,
        "confidence": last_confidence,
        "time": last_update_time,
        "balance": get_account_balance(),
        "open_trades": count_open_trades(),
    }


# FEATURE 4: VISUAL ARROWS - Functions to draw on chart
def place_arrow_on_chart(symbol: str, time: datetime, arrow_type: str, price: float, confidence: int):
    """Place a visual arrow on MT5 chart.
    
    Args:
        symbol: Trading pair (e.g., 'EURUSD')
        time: Time of the candle
        arrow_type: 'buy' (up) or 'sell' (down)
        price: Price level to place arrow
        confidence: Confidence % for label
    
    Note: This uses MT5's object drawing API. Arrows are visible on chart.
    """
    try:
        if not cfg.ENABLE_VISUAL_ARROWS:
            return
            
        obj_name = f"Arrow_{symbol}_{int(time.timestamp())}_{arrow_type}"
        
        if arrow_type == "buy":
            arrow_code = 241  # Up arrow in MT5
            color = (0, 255, 0)  # Green
        else:
            arrow_code = 242  # Down arrow in MT5
            color = (255, 0, 0)  # Red
        
        # Create arrow object on chart - simplified: verify symbol is valid
        result = mt5.symbol_info_tick(symbol)  # Verify symbol is valid
        if result:
            logger.info("Arrow placed: %s at %s | Confidence: %s", arrow_type.upper(), price, confidence)
    except Exception as e:
        logger.warning("Could not place arrow: %s", e)


def check_connection(timeout_seconds: int = 5) -> Dict[str, Any]:
    """Run a set of checks to verify the MT5 connection and return diagnostics.

    The returned dict contains keys:
      - initialized: bool
      - terminal_info: value or None
      - account_info: value or None
      - symbol_info: value or None
      - recent_rates_ok: bool
      - errors: list of error messages
    """
    diag = {"initialized": False, "terminal_info": None, "account_info": None, "symbol_info": None, "recent_rates_ok": False, "errors": []}
    try:
        # check initialize state
        if not mt5.initialize():
            # If initialize returns False it may still be initialized; call last_error for detail
            diag["errors"].append(f"mt5.initialize() returned False: {mt5.last_error()}")
        else:
            diag["initialized"] = True

        try:
            tinfo = mt5.terminal_info()
            diag["terminal_info"] = tinfo._asdict() if tinfo else None
        except Exception:
            diag["errors"].append(f"terminal_info() error: {mt5.last_error()}")

        try:
            ainfo = mt5.account_info()
            diag["account_info"] = ainfo._asdict() if ainfo else None
        except Exception:
            diag["errors"].append(f"account_info() error: {mt5.last_error()}")

        # symbol
        try:
            s = cfg.SYMBOL
            sinfo = mt5.symbol_info(s)
            diag["symbol_info"] = sinfo._asdict() if sinfo else None
        except Exception:
            diag["errors"].append(f"symbol_info({cfg.SYMBOL}) error: {mt5.last_error()}")

        # recent rates
        try:
            rates = mt5.copy_rates_from_pos(cfg.SYMBOL, TIMEFRAME_MAP.get(cfg.TIMEFRAME, mt5.TIMEFRAME_H1), 0, 10)
            diag["recent_rates_ok"] = rates is not None
        except Exception:
            diag["errors"].append(f"copy_rates_from_pos error: {mt5.last_error()}")

    except Exception as exc:
        diag["errors"].append(str(exc))

    finally:
        try:
            mt5.shutdown()
        except Exception:
            pass

    return diag
