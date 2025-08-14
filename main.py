# autiner/main.py
# -*- coding: utf-8 -*-
"""
Autiner — Entry Point
Chạy Telegram bot + Scheduler cho tín hiệu MEXC
"""

import asyncio
from bots.telegram_bot.telegram_bot import run_telegram_bot

if __name__ == "__main__":
    try:
        asyncio.run(run_telegram_bot())
    except (KeyboardInterrupt, SystemExit):
        print("Bot stopped.")
