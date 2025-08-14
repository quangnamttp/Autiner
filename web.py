# web.py
import asyncio
import logging
import os
from fastapi import FastAPI
import httpx
from bot import run_bot

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

app = FastAPI()
PING_URL = os.getenv("PING_URL", "https://autiner.onrender.com")

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(run_bot())
    asyncio.create_task(self_ping_loop())

@app.get("/")
async def root():
    return {"status": "ok"}

async def self_ping_loop():
    async with httpx.AsyncClient() as client:
        while True:
            try:
                await client.get(PING_URL, timeout=10)
                log.info(f"Pinged {PING_URL}")
            except Exception as e:
                log.error(f"Ping failed: {e}")
            await asyncio.sleep(300)
