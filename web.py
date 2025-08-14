# web.py (đặt ở root autiner/)
import asyncio
import logging
import os
from fastapi import FastAPI
import httpx
from bots.telegram_bot.telegram_bot import run_bot

log = logging.getLogger(__name__)

app = FastAPI()

# Ping Render mỗi 5 phút để giữ bot sống
PING_URL = os.getenv("PING_URL", "https://autiner.onrender.com")

@app.on_event("startup")
async def startup_event():
    # Chạy bot Telegram song song với FastAPI
    asyncio.create_task(run_bot())
    asyncio.create_task(self_ping_loop())

@app.get("/")
async def root():
    return {"status": "ok", "message": "Bot is running"}

async def self_ping_loop():
    async with httpx.AsyncClient() as client:
        while True:
            try:
                r = await client.get(PING_URL, timeout=10)
                log.info(f"Pinged {PING_URL}, status {r.status_code}")
            except Exception as e:
                log.error(f"Ping failed: {e}")
            await asyncio.sleep(300)  # 5 phút
