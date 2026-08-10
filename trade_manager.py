"""Trade manager: sizing, entry/exit logic, trailing stop and breakeven.
"""
from typing import Optional
import logging
import asyncio
from decimal import Decimal, ROUND_DOWN
import math
import time
from datetime import datetime, timedelta

from config import cfg
import mt5_connector as mt5c

logger = logging.getLogger("trade_manager")

# Track trades for MAX_TRADES_PER_DAY limit
trades_today = []


def pip_to_price(symbol_info: dict, pip: float) -> float:
    # determine pip size from symbol_info
    # Typical conversion: price change = pip * point
    point = symbol_info.get("point", 0.00001)
    return float(pip) * float(point)


def calculate_lots(account_balance: float, stop_distance: float, risk_percent: float) -> float:
    """Simple fixed fractional sizing using stop_distance in price units.
    This is a placeholder — depending on symbol contract size one may need to adapt.
    """
    risk_amount = account_balance * (risk_percent / 100.0)
    # assume 1 lot risk per 10000 * stop_distance (very rough). User must adapt to broker's contract size.
    if stop_distance <= 0:
        return cfg.LOT_SIZE
    lots = risk_amount / (10000 * stop_distance)
    # clamp to minimum lot size
    min_lot = cfg.LOT_SIZE
    lots = max(min_lot, round(lots, 2))
    return lots


def has_hit_trade_limit() -> bool:
    """Check if we've hit MAX_TRADES_PER_DAY limit."""
    now = datetime.now()
    yesterday = now - timedelta(hours=24)
    
    # Remove trades older than 24 hours
    global trades_today
    trades_today = [t for t in trades_today if t > yesterday]
    
    return len(trades_today) >= cfg.MAX_TRADES_PER_DAY


async def execute_trade(symbol: str, side: str, confidence: int, stop_distance: Optional[float], take_distance: Optional[float]) -> dict:
    """Place trade if meets risk/confidence rules."""
    
    # Check daily trade limit
    if has_hit_trade_limit():
        logger.warning("Daily trade limit reached (%s trades). Skipping.", cfg.MAX_TRADES_PER_DAY)
        return {"status": "rejected", "reason": "daily_limit_reached"}
    
    # Use MIN_CONFIDENCE_TO_TRADE for testing, CONFIDENCE_THRESHOLD for live
    min_conf = cfg.MIN_CONFIDENCE_TO_TRADE if cfg.ENABLE_FORCE_TEST else cfg.CONFIDENCE_THRESHOLD
    if confidence < min_conf:
        logger.debug("Confidence %s%% < threshold %s%%. Skipping trade.", confidence, min_conf)
        return {"status": "rejected", "reason": "low_confidence"}
    
    # check spread
    info = mt5c.symbol_info(symbol)
    if info is None:
        raise RuntimeError("Symbol info unavailable")

    ask = info.get("ask")
    bid = info.get("bid")
    point = info.get("point", 1)
    spread = (ask - bid) if ask is not None and bid is not None else 0
    # convert to pips approx
    try:
        spread_pips = spread / float(point) if point else float('inf')
    except Exception:
        spread_pips = float('inf')
    if spread_pips > cfg.MAX_SPREAD_PIPS:
        logger.warning("Spread too high: %s pips", spread_pips)
        return {"status": "rejected", "reason": "high_spread", "spread_pips": spread_pips}

    # get account info
    account = mt5c.mt5.account_info()
    balance = float(account.balance) if account else 10000.0

    # calculate lot size
    lots = calculate_lots(balance, stop_distance or 0.0001, cfg.RISK_PERCENT)

    # compute absolute SL/TP prices
    tick = mt5c.mt5.symbol_info_tick(symbol)
    if tick is None:
        raise RuntimeError("Tick data unavailable for symbol")
    if side == "buy":
        price = tick.ask
        sl = price - (stop_distance or 0) if stop_distance else None
        tp = price + (take_distance or 0) if take_distance else None
    else:
        price = tick.bid
        sl = price + (stop_distance or 0) if stop_distance else None
        tp = price - (take_distance or 0) if take_distance else None

    # Safe formatting for logging values that may be None
    price_str = f"{price:.5f}" if price is not None else "N/A"
    sl_str = f"{sl:.5f}" if sl is not None else "N/A"
    tp_str = f"{tp:.5f}" if tp is not None else "N/A"

    logger.info("Placing %s %.2fL %s @ %s | SL: %s | TP: %s | Conf: %s%%",
                side.upper(), lots, symbol, price_str, sl_str, tp_str, confidence)

    # send order (blocking call) via executor
    result = await asyncio.to_thread(mt5c.send_order, symbol, side, lots, price, sl, tp)

    # Log MT5 retcode and result dict
    try:
        retcode = result.get('retcode') if isinstance(result, dict) else None
    except Exception:
        retcode = None
    logger.info("Order result retcode=%s result=%s", retcode, result)
    
    # FEATURE 3: Draw arrow on chart
    try:
        mt5c.place_arrow_on_chart(symbol, datetime.now(), side, price if price is not None else 0.0, confidence)
    except Exception:
        logger.exception("Failed to place arrow on chart")
    
    # Track this trade
    global trades_today
    trades_today.append(datetime.now())
    
    # Update dashboard
    try:
        mt5c.set_dashboard_state(side, confidence)
    except Exception:
        logger.exception("Failed to update dashboard state")
    
    return result


async def manage_open_positions(symbol: str) -> None:
    """Monitor positions and apply trailing stop / breakeven.
    This runs periodically from main loop.
    """
    positions = mt5c.get_positions(symbol)
    if positions.empty:
        return
    for _, p in positions.iterrows():
        try:
            ticket = int(p["ticket"])
            entry = float(p["price_open"])
            side = "buy" if int(p["type"]) == mt5c.mt5.POSITION_TYPE_BUY else "sell"
            volume = float(p["volume"])
            current = mt5c.mt5.symbol_info_tick(symbol)
            if current is None:
                continue
            price = current.bid if side == "buy" else current.ask
            # simplistic trailing and breakeven logic
            profit_points = (price - entry) / p.get("point", 0.00001) if side == "buy" else (entry - price) / p.get("point", 0.00001)
            # set breakeven after 15 pips profit
            be_trigger = 15
            trailed = 10
            if profit_points >= be_trigger:
                # modify SL to entry + 1 pip
                new_sl = entry + (0.0001 if side == "buy" else -0.0001)
                # send modify — for simplicity we close and re-open or use order_modify if available
                # Order modification is broker dependent; here we illustrate approach
                logger.info("Would move SL to breakeven for ticket %s to %s", ticket, new_sl)
            if profit_points >= trailed:
                logger.info("Would apply trailing stop for ticket %s", ticket)
        except Exception:
            logger.exception("Error managing position row: %s", p)
