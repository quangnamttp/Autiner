# web.py — Render Web Service + FastAPI + Telegram polling (thread riêng)
# Start Command: uvicorn web:app --host 0.0.0.0 --port $PORT

import os
import threading
import asyncio
import aiohttp
from fastapi import FastAPI
from bots.telegram_bot import build_app

app = FastAPI()

_app = None                 # python-telegram-bot Application
_poll_thread = None         # Thread chạy polling riêng


async def keep_awake():
    """Tự ping chính URL để Render không ngủ. Đặt SELF_URL trong ENV, nếu không có sẽ bỏ qua."""
    url = os.getenv("SELF_URL")
    if not url:
        print("[KEEP_AWAKE] Bỏ qua (không có SELF_URL).")
        return
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                async with session.get(url) as resp:
                    print(f"[KEEP_AWAKE] Ping {url} -> {resp.status}")
            except Exception as e:
                print(f"[KEEP_AWAKE] Lỗi ping {url}: {e}")
            await asyncio.sleep(300)  # 5 phút


def _polling_thread():
    """Chạy run_polling trong event loop riêng tránh xung đột với Uvicorn."""
    global _app
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def runner():
        await _app.run_polling(close_loop=False)

    try:
        loop.run_until_complete(runner())
    finally:
        loop.close()


@app.on_event("startup")
async def startup():
    global _app, _poll_thread
    _app = build_app()                          # Application đã gắn scheduler countdown trong build_app
    _poll_thread = threading.Thread(target=_polling_thread, daemon=True)
    _poll_thread.start()
    # Keep-awake (tùy chọn): đặt SELF_URL=https://<tên-app>.onrender.com/
    asyncio.create_task(keep_awake())
    print("[STARTUP] Bot polling + keep-awake đã chạy.")


@app.on_event("shutdown")
async def shutdown():
    global _app
    if _app:
        await _app.stop()
        await _app.shutdown()
    print("[SHUTDOWN] Bot đã dừng.")


@app.get("/")
async def root():
    return {"status": "ok"}
