# web.py (đặt ở root autiner/)
import asyncio
import logging
import os
from fastapi import FastAPI
import httpx
from bots.telegram_bot.telegram_bot import run_bot

# Bật log toàn hệ thống
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

app = FastAPI()

# URL để ping giữ Render không ngủ
PING_URL = os.getenv("PING_URL", "https://autiner.onrender.com")
PING_INTERVAL = 300  # 5 phút

@app.on_event("startup")
async def startup_event():
    """Chạy bot Telegram và self-ping song song."""
    loop = asyncio.get_event_loop()
    loop.create_task(run_bot())
    loop.create_task(self_ping_loop())
    log.info("🚀 Bot và self-ping đã khởi chạy.")

@app.get("/")
async def root():
    return {"status": "ok", "message": "Bot is running"}

async def self_ping_loop():
    """Ping chính app mỗi 5 phút để giữ cho Render không sleep."""
    while True:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(PING_URL)
                log.info(f"[PING] {PING_URL} status={r.status_code}")
        except Exception as e:
            log.error(f"[PING ERROR] {e}")
        await asyncio.sleep(PING_INTERVAL)
