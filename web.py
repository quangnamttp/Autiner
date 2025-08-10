# Start Command trên Render:
# uvicorn autiner.web:app --host 0.0.0.0 --port $PORT

import os
import asyncio
import aiohttp
from fastapi import FastAPI, Request, HTTPException
from telegram import Update

from autiner.settings import PUBLIC_URL, WEBHOOK_SECRET, SELF_URL
from autiner.bots.telegram_bot.telegram_bot import build_app, send_signals

app = FastAPI()

_application = None           # python-telegram-bot Application
_scheduler_task = None        # task chạy loop gửi tín hiệu theo SLOT_TIMES
_keep_awake_task = None       # task tự ping để Render không ngủ


# --- keep-awake (tuỳ chọn) ---
async def keep_awake():
    url = (SELF_URL or "").rstrip("/")
    if not url:
        return
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                async with session.get(url) as r:
                    print(f"[KEEP_AWAKE] {url} -> {r.status}")
            except Exception as e:
                print(f"[KEEP_AWAKE] error: {e}")
            await asyncio.sleep(300)  # 5 phút
# -----------------------------


@app.on_event("startup")
async def startup():
    global _application, _scheduler_task, _keep_awake_task

    if not PUBLIC_URL or not WEBHOOK_SECRET:
        raise RuntimeError("Thiếu PUBLIC_URL hoặc WEBHOOK_SECRET trong ENV.")

    # Khởi tạo bot application
    _application = build_app()
    await _application.initialize()
    await _application.start()

    # Đăng ký webhook tới endpoint FastAPI
    webhook_url = f"{PUBLIC_URL.rstrip('/')}/webhook/{WEBHOOK_SECRET}"
    await _application.bot.set_webhook(
        url=webhook_url,
        drop_pending_updates=True,
        secret_token=WEBHOOK_SECRET,  # Telegram sẽ gửi header xác thực
    )
    print(f"[STARTUP] Webhook set to: {webhook_url}")

    # Chạy scheduler gửi tín hiệu (đếm ngược + 5 tín hiệu mỗi 30')
    _scheduler_task = asyncio.create_task(send_signals(_application))

    # (tuỳ chọn) giữ Render không ngủ
    _keep_awake_task = asyncio.create_task(keep_awake())


@app.on_event("shutdown")
async def shutdown():
    global _application, _scheduler_task, _keep_awake_task

    # Dừng scheduler
    if _scheduler_task and not _scheduler_task.done():
        _scheduler_task.cancel()
        try:
            await _scheduler_task
        except asyncio.CancelledError:
            pass

    # Dừng keep-awake
    if _keep_awake_task and not _keep_awake_task.done():
        _keep_awake_task.cancel()
        try:
            await _keep_awake_task
        except asyncio.CancelledError:
            pass

    # Tắt bot
    if _application:
        await _application.stop()
        await _application.shutdown()
    print("[SHUTDOWN] stopped")


@app.get("/")
async def root():
    return {"status": "ok"}


@app.post("/webhook/{secret}")
async def tg_webhook(secret: str, request: Request):
    # Xác thực path secret
    if secret != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Invalid webhook secret")

    # Xác thực header do Telegram gửi (tăng bảo mật)
    header_token = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if header_token != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Invalid secret token header")

    data = await request.json()
    update = Update.de_json(data, _application.bot)
    await _application.process_update(update)
    return {"ok": True}
