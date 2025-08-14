# web.py (root autiner/)
import logging
import os
import asyncio
from fastapi import FastAPI, Request
import httpx

from bots.telegram_bot.telegram_bot import application

log = logging.getLogger(__name__)

app = FastAPI()

# URL Render của bạn
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://autiner.onrender.com/webhook")

# Ping Render mỗi 5 phút để giữ bot sống
PING_URL = os.getenv("PING_URL", "https://autiner.onrender.com")


@app.on_event("startup")
async def startup_event():
    # Đặt webhook khi khởi động
    await application.bot.set_webhook(WEBHOOK_URL)
    log.info(f"Webhook set to {WEBHOOK_URL}")

    # Tự ping để giữ bot sống
    asyncio.create_task(self_ping_loop())


@app.post("/webhook")
async def telegram_webhook(req: Request):
    """Nhận update từ Telegram"""
    data = await req.json()
    await application.update_queue.put(data)
    return {"ok": True}


@app.get("/")
async def root():
    return {"status": "ok", "message": "Bot is running"}


async def self_ping_loop():
    """Tự ping chính mình mỗi 5 phút"""
    async with httpx.AsyncClient() as client:
        while True:
            try:
                r = await client.get(PING_URL, timeout=10)
                log.info(f"Pinged {PING_URL}, status {r.status_code}")
            except Exception as e:
                log.error(f"Ping failed: {e}")
            await asyncio.sleep(300)  # 5 phút
