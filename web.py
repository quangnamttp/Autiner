import asyncio
import logging
from fastapi import FastAPI
from bots.telegram_bot import router, setup_bot, send_morning_report, send_night_summary
from settings import settings

log = logging.getLogger(__name__)
app = FastAPI()
app.include_router(router)

@app.on_event("startup")
async def startup_event():
    bot_app = setup_bot(app)
    asyncio.create_task(ping_loop())
    asyncio.create_task(schedule_daily(bot_app))

async def ping_loop():
    import httpx
    while True:
        try:
            async with httpx.AsyncClient() as client:
                await client.get("https://autiner.onrender.com")
        except:
            pass
        await asyncio.sleep(300)

async def schedule_daily(bot_app):
    while True:
        now = bot_app.application_context.now_vn()
        if now.strftime("%H:%M") == "06:00":
            await send_morning_report(bot_app)
        elif now.strftime("%H:%M") == "22:00":
            await send_night_summary(bot_app)
        await asyncio.sleep(60)
