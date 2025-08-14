# web.py
import asyncio
import datetime as dt
import httpx
from fastapi import FastAPI
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from bots.telegram_bot.telegram_bot import send_signal_batch, send_morning_report, send_night_summary
import settings

# Tạo FastAPI app
app = FastAPI()

# Scheduler
scheduler = AsyncIOScheduler(timezone="Asia/Ho_Chi_Minh")

# Ping tới chính Render để không bị sleep
PING_URL = "https://autiner.onrender.com"

async def ping_self():
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(PING_URL)
            print(f"[PING] {dt.datetime.now()} → {r.status_code}")
    except Exception as e:
        print(f"[PING ERROR] {e}")

# Các job
async def job_morning():
    await send_morning_report()

async def job_night():
    await send_night_summary()

async def job_signals():
    await send_signal_batch()

# Khởi động scheduler khi server start
@app.on_event("startup")
async def startup_event():
    # Ping 5 phút/lần
    scheduler.add_job(lambda: asyncio.create_task(ping_self()), "interval", minutes=5)

    # Bản tin sáng 06:00
    scheduler.add_job(lambda: asyncio.create_task(job_morning()), "cron", hour=6, minute=0)

    # Tín hiệu 06:15 → 21:45 mỗi 30 phút
    for h in range(6, 22):
        for m in [15, 45]:
            scheduler.add_job(lambda: asyncio.create_task(job_signals()), "cron", hour=h, minute=m)

    # Tổng kết 22:00
    scheduler.add_job(lambda: asyncio.create_task(job_night()), "cron", hour=22, minute=0)

    scheduler.start()
    print("🚀 Scheduler started")

# Endpoint check
@app.get("/")
async def root():
    return {"status": "running", "time": dt.datetime.now().isoformat()}
