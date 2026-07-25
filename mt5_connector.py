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

        logger.info("MT5 initialized and logged in")
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
