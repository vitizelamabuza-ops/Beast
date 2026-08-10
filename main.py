"""Main executor that ties everything together.
Run this file as an entrypoint. The bot will poll market data periodically and attempt trades when conditions are met.

FEATURES:
1. Debug Mode - Print indicator values every tick
2. Force Test Button - Trigger a test BUY signal
3. Visual Arrows - Draw arrows on chart for signals
4. Live Dashboard - Show bot status on chart
5. Lower confidence threshold for testing
"""
import asyncio
import logging
from datetime import datetime
from logger import setup_logging
from config import cfg
import mt5_connector as mt5c
from strategy import generate_signal
from trade_manager import execute_trade, manage_open_positions


logger = logging.getLogger("main")

# Track force test state
force_test_used = False


async def bot_loop():
    """Main bot loop - runs every POLL_INTERVAL seconds."""
    global force_test_used
    
    ok = mt5c.initialize()
    if not ok:
        logger.error("MT5 initialization failed, exiting")
        return

    logger.info("="*80)
    logger.info("BEAST BOT STARTED")
    logger.info(f"Symbol: {cfg.SYMBOL} | Timeframe: {cfg.TIMEFRAME}")
    logger.info(f"Confidence Threshold: {cfg.CONFIDENCE_THRESHOLD}%")
    logger.info(f"Min Confidence to Trade: {cfg.MIN_CONFIDENCE_TO_TRADE}%")
    logger.info(f"Debug Mode: {cfg.DEBUG_MODE}")
    logger.info(f"Force Test Enabled: {cfg.ENABLE_FORCE_TEST}")
    logger.info(f"Visual Arrows: {cfg.ENABLE_VISUAL_ARROWS}")
    logger.info(f"Dashboard: {cfg.ENABLE_DASHBOARD}")
    logger.info(f"Max Trades/Day: {cfg.MAX_TRADES_PER_DAY}")
    logger.info("="*80)

    try:
        loop_count = 0
        while True:
            try:
                loop_count += 1
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                logger.info(f"\nLoop #{loop_count} at {current_time}")
                
                # Get market data
                df = await mt5c.get_rates_async(cfg.SYMBOL, cfg.TIMEFRAME, cfg.HIST_PERIODS)
                
                # FEATURE 2: FORCE TEST - Use on first iteration if enabled
                force_buy = False
                if cfg.ENABLE_FORCE_TEST and not force_test_used:
                    force_buy = True
                    force_test_used = True
                    logger.warning("FORCE TEST MODE ACTIVATED - Will send test trade")
                
                # Generate signal
                signal = generate_signal(df, force_buy=force_buy)
                
                # FEATURE 1: DEBUG MODE - Log all details
                if cfg.DEBUG_MODE:
                    logger.info(
                        f"\nSIGNAL DETAILS:\n"
                        f"  Signal: {signal['signal'].upper()}\n"
                        f"  Confidence: {signal['confidence']}%\n"
                        f"  RSI(14): {signal.get('rsi', 0):.2f}\n"
                        f"  EMA50: {signal.get('ema50', 0):.5f}\n"
                        f"  EMA200: {signal.get('ema200', 0):.5f}\n"
                        f"  Price: {df['close'].iloc[-1]:.5f}\n"
                        f"  ATR: {signal.get('atr', 0):.6f}\n"
                        f"  Reasons: {signal['reasons']}"
                    )
                else:
                    logger.info(
                        f"Signal: {signal['signal'].upper()} | "
                        f"Confidence: {signal['confidence']}% | "
                        f"RSI: {signal.get('rsi', 0):.2f}"
                    )
                
                # FEATURE 4: LIVE DASHBOARD
                if cfg.ENABLE_DASHBOARD:
                    balance = mt5c.get_account_balance()
                    open_trades = mt5c.count_open_trades(cfg.SYMBOL)
                    logger.info(
                        f"\nDASHBOARD:\n"
                        f"  Status: LIVE\n"
                        f"  Last Update: {current_time}\n"
                        f"  Last Signal: {signal['signal'].upper()}\n"
                        f"  Confidence: {signal['confidence']}%\n"
                        f"  Open Trades: {open_trades}\n"
                        f"  Balance: ${balance:,.2f}"
                    )
                
                # Check if we should trade
                min_conf_threshold = cfg.MIN_CONFIDENCE_TO_TRADE if cfg.ENABLE_FORCE_TEST else cfg.CONFIDENCE_THRESHOLD
                
                if signal["confidence"] >= min_conf_threshold and signal["signal"] in ("buy", "sell"):
                    logger.info(f"\nTRADE SIGNAL CONFIRMED | Executing {signal['signal'].upper()}...")
                    result = await execute_trade(
                        cfg.SYMBOL,
                        signal["signal"],
                        signal["confidence"],
                        signal["stop_distance"],
                        signal["take_distance"]
                    )
                    if result.get("retcode") == 10009:  # TRADE_RETCODE_DONE
                        logger.info("Trade EXECUTED successfully")
                    else:
                        logger.warning(f"Trade result: {result}")
                else:
                    if cfg.DEBUG_MODE:
                        logger.debug(
                            f"No trade - Confidence {signal['confidence']}% < threshold {min_conf_threshold}% "
                            f"or signal is '{signal['signal']}'"
                        )

                # manage open positions
                await manage_open_positions(cfg.SYMBOL)

            except Exception as e:
                logger.exception(f"Error in main loop: {e}")

            # Wait for next check
            logger.debug(f"Sleeping for {cfg.POLL_INTERVAL}s...")
            await asyncio.sleep(cfg.POLL_INTERVAL)
    finally:
        mt5c.shutdown()
        logger.info("Bot stopped")


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
