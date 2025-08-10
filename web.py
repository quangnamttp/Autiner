# web.py — Webhook + FastAPI (Render)
# Start Command: uvicorn web:app --host 0.0.0.0 --port $PORT

import os
import asyncio
import aiohttp
from fastapi import FastAPI, Request, HTTPException
from telegram import Update
from bots.telegram_bot import build_app

app = FastAPI()

application = None  # python-telegram-bot Application
keep_awake_task = None

# -------- keep-awake (tuỳ chọn) --------
async def keep_awake():
    url = os.getenv("SELF_URL")
    if not url:
        return
    async with aiohttp.ClientSession() as s:
        while True:
            try:
                async with s.get(url) as r:
                    print(f"[KEEP_AWAKE] {url} -> {r.status}")
            except Exception as e:
                print(f"[KEEP_AWAKE] error: {e}")
            await asyncio.sleep(300)  # 5 phút
# --------------------------------------


@app.on_event("startup")
async def startup():
    global application, keep_awake_task
    public_url = os.getenv("PUBLIC_URL")
    secret = os.getenv("WEBHOOK_SECRET")
    if not public_url or not secret:
        raise RuntimeError("Thiếu PUBLIC_URL hoặc WEBHOOK_SECRET trong ENV.")

    application = build_app()
    await application.initialize()
    await application.start()

    # Đặt webhook trỏ về FastAPI endpoint của chúng ta
    webhook_url = f"{public_url}/webhook/{secret}"
    await application.bot.set_webhook(
        url=webhook_url,
        drop_pending_updates=True,
        secret_token=secret  # Telegram sẽ gửi header X-Telegram-Bot-Api-Secret-Token
    )
    print(f"[STARTUP] Webhook set to: {webhook_url}")

    # keep-awake (tuỳ chọn)
    keep_awake_task = asyncio.create_task(keep_awake())


@app.on_event("shutdown")
async def shutdown():
    global application, keep_awake_task
    if keep_awake_task and not keep_awake_task.done():
        keep_awake_task.cancel()
        try:
            await keep_awake_task
        except asyncio.CancelledError:
            pass
    if application:
        await application.stop()
        await application.shutdown()
    print("[SHUTDOWN] stopped")


@app.get("/")
async def root():
    return {"status": "ok"}


@app.post("/webhook/{secret}")
async def tg_webhook(secret: str, request: Request):
    # Xác thực secret path và header
    expected = os.getenv("WEBHOOK_SECRET")
    if secret != expected:
        raise HTTPException(status_code=401, detail="Invalid webhook secret")

    # (Tuỳ) kiểm tra header secret từ Telegram
    header_token = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if header_token != expected:
        raise HTTPException(status_code=401, detail="Invalid secret token header")

    data = await request.json()
    update = Update.de_json(data, application.bot)
    # Đưa update vào app xử lý
    await application.process_update(update)
    return {"ok": True}
