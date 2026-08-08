# Bybit Crypto Screener

A Python-based Telegram bot for analyzing the Bybit cryptocurrency market and identifying coins with potential for significant future price movements.

## 🎯 Goal

The project is designed to detect unusual market activity and find cryptocurrencies that may have the potential to become future top gainers.

The scanner currently focuses on abnormal volume activity, with additional market analysis planned for future versions.

## ⚙️ Current Features

- Bybit market scanning
- 1H timeframe analysis
- USDT pairs
- Abnormal volume detection
- VolRatio-based filtering
- Telegram notifications
- Automatic periodic scanning
- Manual market scanning

## 🚧 Project Status

**Work in progress.**

The current version contains the initial scanning logic. More market filters and analysis features are planned.

Future development may include:

- Price action analysis
- Open Interest
- Volatility analysis
- Additional market indicators
- Improved signal filtering
- Historical signal testing

## 🛠️ Tech Stack

- Python
- Bybit API
- Pybit
- Aiogram
- APScheduler
- Telegram Bot API

## 📁 Project Structure

```text
bybit-crypto-screener/
├── bot.py
├── scanner.py
├── bybit_api.py
├── config.py
├── requirements.txt
├── .env.example
└── README.md
