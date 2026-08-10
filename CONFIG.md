Configuration for MetaTrader 5 bot

Required environment variables

- MT5_TERMINAL_PATH (preferred): Full filesystem path to the MetaTrader 5 terminal executable you want the bot to use. Example:
  C:\\Program Files\\MetaTrader 5\\terminal64.exe

- MT5_PATH (legacy): Older name used in the project. If both are provided MT5_TERMINAL_PATH is preferred.

- MT5_LOGIN (optional): Numeric login ID for the demo account. If provided the bot will attempt to login programmatically.
- MT5_PASSWORD (optional): Password for the account. Keep this secret and never commit.
- MT5_SERVER (optional): Broker server name if required by login.

Other useful environment variables (already present in .env.example)
- SYMBOL, TIMEFRAME, LOT_SIZE, RISK_PERCENT, CONFIDENCE_THRESHOLD, MIN_CONFIDENCE_TO_TRADE
- POLL_INTERVAL, MAX_SPREAD_PIPS, HIST_PERIODS, DEBUG_MODE, ENABLE_FORCE_TEST

How to test the connection (safe, non-trading):
1. Ensure MetaTrader 5 terminal is installed and you can open it manually.
2. Set MT5_TERMINAL_PATH to the terminal64.exe path if the terminal is not already running.
3. From the repository root run the diagnostic:
   python -c "import json; from mt5_connector import check_connection; print(json.dumps(check_connection(), indent=2, ensure_ascii=False))"

Interpretation of diagnostic fields:
- initialized: Whether mt5.initialize() succeeded
- terminal_info: Information from mt5.terminal_info() if available
- account_info: Information from mt5.account_info() if available
- symbol_info: Information from mt5.symbol_info(SYMBOL)
- recent_rates_ok: True if copy_rates_from_pos returned data
- errors: list of collected error messages

If diagnostics show initialized=true, account_info present, symbol_info present, and recent_rates_ok=true then the bot is ready to start trading.

Security and safety notes:
- Do not store real credentials in version control. Use a local .env file or a secret manager.
- Test with a DEMO account only.
- The connector will not place trades just to test connectivity.
