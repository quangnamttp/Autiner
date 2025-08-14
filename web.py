# autiner/web.py
# -*- coding: utf-8 -*-
"""
FastAPI Webhook + Scheduler Autiner
- Kết hợp web server cho Telegram Webhook
- Tích hợp luôn scheduler để gửi tín hiệu & ping 5 phút
"""

from fastapi import FastAPI, Request
import asyncio
import aiohttp
import os
import logging
from datetime import datetime
from telegram import Bot
from telegram.constants import ParseMode
from telegram.ext import Application
import pytz

# ======= LOGGING =======
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("autiner")

# ======= SETTINGS =======
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TZ_NAME = os.getenv("TZ_NAME", "Asia/Ho_Chi_Minh")

# Tự import generate_signals từ signal_engine
from bots.signals.signal_engine import generate_signals

# ======= FASTAPI APP =======
app = FastAPI()

@app.get("/")
async def root():
    return {"status": "ok", "time": datetime.now().isoformat()}

@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    log.info(f"Webhook data: {data}")
    return {"ok": True}

# ======= PING RENDER =======
PING_URL = "https://autiner.onrender.com"

async def ping_self():
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(PING_URL) as resp:
                log.info(f"Ping {PING_URL} => {resp.status}")
        except Exception as e:
            log.error(f"Ping error: {e}")

# ======= SEND SIGNALS =======
async def send_signals():
    bot = Bot(token=TELEGRAM_TOKEN)
    tz = pytz.timezone(TZ_NAME)
    now = datetime.now(tz).strftime("%H:%M:%S")
    signals = generate_signals(unit="VND", n=5)
    if not signals:
        await bot.send_message(chat_id=CHAT_ID, text=f"⛔ {now} — Không có tín hiệu")
        return
    for s in signals:
        msg = (
            f"⚡ <b>{s['token']}</b> — {s['side']}\n"
            f"Loại: {s['orderType']}\n"
            f"Entry: {s['entry']}\n"
            f"TP: {s['tp']}\n"
            f"SL: {s['sl']}\n"
            f"Độ mạnh: {s['strength']}%\n\n"
            f"<i>{s['reason']}</i>"
        )
        await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode=ParseMode.HTML)

# ======= SCHEDULER =======
async def scheduler():
    while True:
        # Ping mỗi 5 phút
        await ping_self()

        # Gửi tín hiệu mỗi 30 phút (06:15 – 21:45)
        tz = pytz.timezone(TZ_NAME)
        now = datetime.now(tz)
        minute = now.minute
        hour = now.hour
        if (hour >= 6 and hour <= 21) and (minute in (15, 45)):
            await send_signals()

        await asyncio.sleep(60)  # check mỗi phút

# ======= STARTUP =======
@app.on_event("startup")
async def on_startup():
    asyncio.create_task(scheduler())
    log.info("Scheduler started")
