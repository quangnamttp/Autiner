# web.py — dùng cho Render (Start Command: uvicorn web:app --host 0.0.0.0 --port $PORT)
import asyncio
from fastapi import FastAPI
from bots.telegram_bot import build_app

app = FastAPI()

telegram_app = None
_poll_task: asyncio.Task | None = None

@app.on_event("startup")
async def startup():
    global telegram_app, _poll_task
    telegram_app = build_app()
    await telegram_app.initialize()
    await telegram_app.start()  # KHÔNG dùng run_polling ở đây
    _poll_task = asyncio.create_task(telegram_app.updater.start_polling())  # chạy trong loop hiện tại

@app.on_event("shutdown")
async def shutdown():
    global telegram_app, _poll_task
    if _poll_task and not _poll_task.done():
        await telegram_app.updater.stop()
        _poll_task.cancel()
        try:
            await _poll_task
        except asyncio.CancelledError:
            pass
    if telegram_app:
        await telegram_app.stop()
        await telegram_app.shutdown()

@app.get("/")
async def root():
    return {"status": "ok"}
