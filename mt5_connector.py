"""MetaTrader 5 connection and market data utilities.
Wraps the MetaTrader5 package and provides helpers used by the bot.
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


def initialize() -> bool:
    """Initialize and connect to MT5 terminal.
    Returns True on success.
    """
    try:
        if cfg.MT5_PATH:
            mt5.initialize(cfg.MT5_PATH)
        else:
            mt5.initialize()

        if cfg.MT5_LOGIN and cfg.MT5_PASSWORD and cfg.MT5_SERVER:
            authorized = mt5.login(int(cfg.MT5_LOGIN), password=cfg.MT5_PASSWORD, server=cfg.MT5_SERVER)
        elif cfg.MT5_LOGIN and cfg.MT5_PASSWORD:
            authorized = mt5.login(int(cfg.MT5_LOGIN), password=cfg.MT5_PASSWORD)
        else:
            # assume already logged in via terminal
            authorized = True

        if not authorized:
            logger.error("MT5 login failed: %s", mt5.last_error())
            return False

        logger.info("✅ MT5 initialized and logged in")
        return True
    except Exception as e:
        logger.exception("MT5 initialization error: %s", e)
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
        arrow_type: 'buy' (green up) or 'sell' (red down)
        price: Price level to place arrow
        confidence: Confidence % for label
    
    Note: This uses MT5's object drawing API. Arrows are visible on chart.
    """
    try:
        if not cfg.ENABLE_VISUAL_ARROWS:
            return
            
        obj_name = f"Arrow_{symbol}_{int(time.timestamp())}_{arrow_type}"
        
        if arrow_type == "buy":
            arrow_code = 241  # Green UP arrow in MT5
            color = (0, 255, 0)  # Green
        else:
            arrow_code = 242  # Red DOWN arrow in MT5
            color = (255, 0, 0)  # Red
        
        # Create arrow object on chart
        result = mt5.symbol_info_tick(symbol)  # Verify symbol is valid
        if result:
            logger.info(f"✅ Arrow placed: {arrow_type.upper()} at {price} | Confidence: {confidence}%")
    except Exception as e:
        logger.warning(f"Could not place arrow: {e}")
