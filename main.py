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

    # Run a quick diagnostic to make sure account, symbol and recent rates are available
    diag = mt5c.check_connection()
    if not diag.get("initialized"):
        logger.error("MT5 diagnostic failed: %s", diag.get("errors"))
        mt5c.shutdown()
        return
    if diag.get("symbol_info") is None:
        logger.error("Required symbol not available: %s", cfg.SYMBOL)
        mt5c.shutdown()
        return
    if not diag.get("recent_rates_ok"):
        logger.error("No recent market data available for symbol %s", cfg.SYMBOL)
        mt5c.shutdown()
        return

    logger.info("BEAST BOT STARTED")
    logger.info("Symbol: %s | Timeframe: %s", cfg.SYMBOL, cfg.TIMEFRAME)
    logger.info("Confidence Threshold: %s%%", cfg.CONFIDENCE_THRESHOLD)
    logger.info("Min Confidence to Trade: %s%%", cfg.MIN_CONFIDENCE_TO_TRADE)
    logger.info("Debug Mode: %s", cfg.DEBUG_MODE)
    logger.info("Force Test Enabled: %s", cfg.ENABLE_FORCE_TEST)
    logger.info("Visual Arrows: %s", cfg.ENABLE_VISUAL_ARROWS)
    logger.info("Dashboard: %s", cfg.ENABLE_DASHBOARD)
    logger.info("Max Trades/Day: %s", cfg.MAX_TRADES_PER_DAY)

    try:
        loop_count = 0
        while True:
            try:
                loop_count += 1
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                logger.info("Loop #%d at %s", loop_count, current_time)
                
                # Get market data
                df = await mt5c.get_rates_async(cfg.SYMBOL, cfg.TIMEFRAME, cfg.HIST_PERIODS)
                if df is None or df.empty:
                    logger.warning("No rates data returned for %s", cfg.SYMBOL)
                    await asyncio.sleep(cfg.POLL_INTERVAL)
                    continue
                
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
                        "SIGNAL DETAILS: Signal=%s Confidence=%s RSI=%.2f EMA50=%.5f EMA200=%.5f Price=%.5f ATR=%.6f Reasons=%s",
                        signal.get("signal", "hold").upper(),
                        signal.get("confidence", 0),
                        signal.get("rsi", 0.0),
                        signal.get("ema50", 0.0),
                        signal.get("ema200", 0.0),
                        float(df['close'].iloc[-1]) if 'close' in df.columns and not df['close'].empty else 0.0,
                        signal.get("atr", 0.0),
                        signal.get('reasons')
                    )
                else:
                    logger.info("Signal: %s | Confidence: %s%% | RSI: %.2f",
                                signal.get('signal', 'hold').upper(),
                                signal.get('confidence', 0),
                                signal.get('rsi', 0.0))
                
                # FEATURE 4: LIVE DASHBOARD
                if cfg.ENABLE_DASHBOARD:
                    balance = mt5c.get_account_balance()
                    open_trades = mt5c.count_open_trades(cfg.SYMBOL)
                    logger.info("DASHBOARD: Status=LIVE LastUpdate=%s LastSignal=%s Confidence=%s%% OpenTrades=%s Balance=$%s",
                                current_time,
                                signal.get('signal', 'hold').upper(),
                                signal.get('confidence', 0),
                                open_trades,
                                f"{balance:,.2f}")
                
                # Check if we should trade
                min_conf_threshold = cfg.MIN_CONFIDENCE_TO_TRADE if cfg.ENABLE_FORCE_TEST else cfg.CONFIDENCE_THRESHOLD
                
                if signal["confidence"] >= min_conf_threshold and signal["signal"] in ("buy", "sell"):
                    logger.info("TRADE SIGNAL CONFIRMED | Executing %s...", signal['signal'].upper())
                    result = await execute_trade(
                        cfg.SYMBOL,
                        signal["signal"],
                        signal["confidence"],
                        signal["stop_distance"],
                        signal["take_distance"]
                    )
                    # result is expected to be a dict from mt5
                    retcode = result.get('retcode') if isinstance(result, dict) else None
                    if retcode == 10009:  # TRADE_RETCODE_DONE
                        logger.info("Trade executed successfully")
                    else:
                        logger.warning("Trade result: %s", result)
                else:
                    if cfg.DEBUG_MODE:
                        logger.debug("No trade - Confidence %s%% < threshold %s%% or signal is '%s'",
                                     signal.get('confidence', 0), min_conf_threshold, signal.get('signal', 'hold'))

                # manage open positions
                await manage_open_positions(cfg.SYMBOL)

            except Exception as e:
                logger.exception("Error in main loop: %s", e)

            # Wait for next check
            logger.debug("Sleeping for %s seconds...", cfg.POLL_INTERVAL)
            await asyncio.sleep(cfg.POLL_INTERVAL)
    finally:
        mt5c.shutdown()
        logger.info("Bot stopped")


def main():
    setup_logging()
    logger.info("Starting bot for %s %s", cfg.SYMBOL, cfg.TIMEFRAME)
    try:
        asyncio.run(bot_loop())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")


if __name__ == "__main__":
    main()
