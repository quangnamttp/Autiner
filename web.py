# web.py (root autiner/)
import asyncio
import logging
import os
from fastapi import FastAPI, Request
import httpx

from bots.telegram_bot.telegram_bot import run_bot, handle_webhook
from settings import settings

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

app = FastAPI()

PING_URL = os.getenv("PING_URL", "https://autiner.onrender.com")

@app.on_event("startup")
async def startup_event():
    # Chạy bot Telegram song song (webhook mode)
    asyncio.create_task(run_bot(webhook_mode=True))
    # Chạy ping để Render không sleep
    asyncio.create_task(self_ping_loop())

@app.get("/")
async def root():
    return {"status": "ok", "message": "Bot is running"}

@app.post("/webhook")
async def webhook_handler(request: Request):
    data = await request.json()
    await handle_webhook(data)
    return {"status": "ok"}

async def self_ping_loop():
    async with httpx.AsyncClient() as client:
        while True:
            try:
                r = await client.get(PING_URL, timeout=10)
                log.info(f"Pinged {PING_URL}, status {r.status_code}")
            except Exception as e:
                log.error(f"Ping failed: {e}")
            await asyncio.sleep(300)  # 5 phút
