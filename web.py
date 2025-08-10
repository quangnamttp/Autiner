# web.py — chạy trên Render (Web Service) với FastAPI + uvicorn
# Start Command trên Render:
# uvicorn web:app --host 0.0.0.0 --port $PORT

import asyncio
from fastapi import FastAPI
from bots.telegram_bot import build_app

app = FastAPI()

telegram_app = None          # python-telegram-bot Application
_polling_task: asyncio.Task | None = None  # task chạy polling

@app.on_event("startup")
async def startup():
    global telegram_app, _polling_task
    telegram_app = build_app()                 # tạo Application (đã gắn scheduler nền)
    await telegram_app.initialize()            # init handlers, etc.
    # chạy polling trong background để nhận /start, /demo...
    _polling_task = asyncio.create_task(
        telegram_app.run_polling(close_loop=False)
    )

@app.on_event("shutdown")
async def shutdown():
    global telegram_app, _polling_task
    # dừng polling trước
    if _polling_task and not _polling_task.done():
        _polling_task.cancel()
        try:
            await _polling_task
        except asyncio.CancelledError:
            pass
    # stop & shutdown Application
    if telegram_app:
        await telegram_app.stop()
        await telegram_app.shutdown()

@app.get("/")
async def root():
    return {"status": "ok"}
