# Start Command trên Render:
# uvicorn autiner.web:app --host 0.0.0.0 --port $PORT

import os
import asyncio
import aiohttp
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from telegram import Update
from telegram.error import TelegramError

from autiner.settings import PUBLIC_URL, WEBHOOK_SECRET, SELF_URL
from autiner.bots.telegram_bot.telegram_bot import build_app, send_signals

_application = None           # python-telegram-bot Application
_scheduler_task = None        # task loop gửi tín hiệu theo SLOT_TIMES
_keep_awake_task = None       # task tự ping để Render không ngủ
_webhook_task = None          # task set webhook (không chặn startup)

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

async def set_webhook_bg():
    """Đặt webhook ở background, không chặn app startup."""
    global _application
    if not PUBLIC_URL or not WEBHOOK_SECRET:
        print("[WEBHOOK] thiếu PUBLIC_URL hoặc WEBHOOK_SECRET, bỏ qua.")
        return
    webhook_url = f"{PUBLIC_URL.rstrip('/')}/webhook/{WEBHOOK_SECRET}"
    try:
        # timeout ngắn để không block startup nếu Telegram chậm
        await asyncio.wait_for(
            _application.bot.set_webhook(
                url=webhook_url,
                drop_pending_updates=True,
                secret_token=WEBHOOK_SECRET,
            ),
            timeout=10
        )
        print(f"[WEBHOOK] set to: {webhook_url}")
    except (asyncio.TimeoutError, TelegramError, Exception) as e:
        print(f"[WEBHOOK] set failed: {e}. Sẽ thử lại sau 30s.")
        # retry nhẹ
        await asyncio.sleep(30)
        try:
            await _application.bot.set_webhook(
                url=webhook_url,
                drop_pending_updates=True,
                secret_token=WEBHOOK_SECRET,
            )
            print(f"[WEBHOOK] set to: {webhook_url} (retry OK)")
        except Exception as e2:
            print(f"[WEBHOOK] retry failed: {e2}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _application, _scheduler_task, _keep_awake_task, _webhook_task
    # Khởi tạo bot
    _application = build_app()
    await _application.initialize()
    await _application.start()

    # Chạy scheduler gửi tín hiệu (đếm ngược + 5 tín hiệu mỗi 30’)
    _scheduler_task = asyncio.create_task(send_signals(_application))

    # (tuỳ chọn) giữ Render không ngủ
    _keep_awake_task = asyncio.create_task(keep_awake())

    # Đặt webhook ở background (không chặn health check)
    _webhook_task = asyncio.create_task(set_webhook_bg())

    print("[STARTUP] FastAPI ready, bot started, background tasks running")
    try:
        yield
    finally:
        # shutdown
        for task in (_scheduler_task, _keep_awake_task, _webhook_task):
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        if _application:
            await _application.stop()
            await _application.shutdown()
        print("[SHUTDOWN] stopped")

app = FastAPI(lifespan=lifespan)

@app.get("/")
async def root():
    return {"status": "ok"}

@app.post("/webhook/{secret}")
async def tg_webhook(secret: str, request: Request):
    if secret != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Invalid webhook secret")
    header_token = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if header_token != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Invalid secret token header")
    data = await request.json()
    update = Update.de_json(data, _application.bot)
    await _application.process_update(update)
    return {"ok": True}
