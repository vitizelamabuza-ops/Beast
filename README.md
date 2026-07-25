# MetaTrader5 Python trading bot

This repository contains a production-oriented MetaTrader 5 forex trading bot written in Python.

Features
- Structured, modular design: config, indicators, strategy, MT5 connector, trade manager, logger, and main loop
- Indicators: EMA, RSI, ATR, MACD, ADX
- Strategy that combines trend, momentum, volatility and confirmation
- Confidence scoring (0-100). Bot only trades if confidence >= CONFIDENCE_THRESHOLD (default 85)
- ATR-based stop loss and take profit
- Risk-based position sizing (RISK_PERCENT per trade)
- Trailing stop and breakeven logic scaffold
- Async-friendly main loop

Setup
1. Create a virtualenv and install dependencies:
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt

2. Copy .env.example to .env and set your MT5 credentials and preferences.

3. Ensure MetaTrader 5 terminal is installed and that the MetaTrader5 Python package can connect.
   On Windows you may need to set MT5_PATH to the terminal64.exe path.

Usage
   python main.py

Notes and important cautions
- This bot is a robust scaffold and is designed to be a strong starting point. It is NOT a plug-and-play guarantee of profitability.
- The lot-sizing function is a simplified placeholder. Adapt it to your broker's contract specifications (contract size, tick value).
- The bot assumes you understand live trading risks. Test thoroughly in a demo environment before going live.
- Consider adding order modification (modify SL/TP) and more precise broker-compatible logic for order types.
