"""Main executor that ties everything together.
Run this file as an entrypoint. The bot will poll market data periodically and attempt trades when conditions are met.
"""
import asyncio
import logging
from logger import setup_logging
from config import cfg
import mt5_connector as mt5c
from strategy import generate_signal
from trade_manager import execute_trade, manage_open_positions


logger = logging.getLogger("main")


async def bot_loop():
    ok = mt5c.initialize()
    if not ok:
        logger.error("MT5 initialization failed, exiting")
        return

    try:
        while True:
            try:
                df = await mt5c.get_rates_async(cfg.SYMBOL, cfg.TIMEFRAME, cfg.HIST_PERIODS)
                signal = generate_signal(df)
                logger.info("Signal: %s", signal)
                if signal["confidence"] >= cfg.CONFIDENCE_THRESHOLD and signal["signal"] in ("buy", "sell"):
                    # compute distances already in price units
                    # signal returns atr-based distances - scale by pair specific point
                    result = await execute_trade(cfg.SYMBOL, signal["signal"], signal["confidence"], signal["stop_distance"], signal["take_distance"])
                    logger.info("Trade result: %s", result)
                else:
                    logger.debug("No trade - confidence or signal not sufficient")

                # manage open positions
                await manage_open_positions(cfg.SYMBOL)

            except Exception:
                logger.exception("Error in main loop")

            await asyncio.sleep(cfg.POLL_INTERVAL)
    finally:
        mt5c.shutdown()


def main():
    setup_logging()
    logger.info("Starting bot for %s %s", cfg.SYMBOL, cfg.TIMEFRAME)
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(bot_loop())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        loop.close()


if __name__ == "__main__":
    main()
