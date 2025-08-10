import asyncio
from fastapi import FastAPI
from bots.telegram_bot import build_app

app = FastAPI()
telegram_app = None  # python-telegram-bot Application

@app.on_event("startup")
async def startup():
    global telegram_app
    telegram_app = build_app()
    await telegram_app.initialize()
    await telegram_app.start()  # chạy bot + scheduler nền

@app.on_event("shutdown")
async def shutdown():
    global telegram_app
    if telegram_app:
        await telegram_app.stop()
        await telegram_app.shutdown()

@app.get("/")
async def root():
    return {"status": "ok"}
