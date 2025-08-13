# web.py
# -*- coding: utf-8 -*-
"""
Webhook server (FastAPI) cho Telegram bot + tự ping keep-alive cho Render.

• Endpoint:
  - GET  /            -> "OK" (health)
  - GET  /health      -> "OK" (health)
  - POST /tg/<TOKEN>  -> Webhook Telegram (TOKEN lấy từ env TELEGRAM_BOT_TOKEN)

• Khởi động:
  - build_app() từ bots/telegram_bot/telegram_bot.py
  - initialize + start Application (python-telegram-bot v20+)
  - setWebhook về WEBHOOK_BASE_URL + /tg/<TOKEN>
  - tạo background task tự ping /health mỗi 4 phút

ENV cần:
  TELEGRAM_BOT_TOKEN   (bắt buộc)
  WEBHOOK_BASE_URL     (ví dụ: https://autiner.onrender.com)
  TZ_NAME, ALLOWED_USER_ID, DEFAULT_UNIT, ...
"""

from __future__ import annotations
import os
import asyncio
from typing import Optional

import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.responses import PlainTextResponse
from telegram import Update
from telegram.ext import Application

from settings import TELEGRAM_BOT_TOKEN

# app PTB đã được cấu hình handler + jobs bên trong
# (file bạn đã có: Autiner/bots/telegram_bot/telegram_bot.py)
from Autiner.bots.telegram_bot.telegram_bot import build_app as build_telegram_application

# ---------- FastAPI ----------
app = FastAPI(title="Autiner Webhook")

# Globals
_application: Optional[Application] = None
_webhook_task = None
_self_ping_task = None

# ---------- Health endpoints ----------
@app.get("/", response_class=PlainTextResponse)
@app.get("/health", response_class=PlainTextResponse)
async def health() -> str:
    return "OK"

# ---------- Telegram webhook ----------
@app.post(f"/tg/{TELEGRAM_BOT_TOKEN}")
async def telegram_webhook(req: Request) -> Response:
    global _application
    if _application is None:
        # chưa sẵn sàng
        return Response(status_code=503)
    data = await req.json()
    try:
        update = Update.de_json(data=data, bot=_application.bot)
        # đẩy vào hàng đợi để PTB xử lý (không block FastAPI)
        await _application.update_queue.put(update)
    except Exception:
        # dữ liệu không hợp lệ
        return Response(status_code=400)
    return Response(status_code=200)

# ---------- Tự ping giữ dịch vụ không ngủ ----------
async def _self_ping_loop():
    base = os.getenv("WEBHOOK_BASE_URL", "").rstrip("/")
    if not base:
        return  # không tự ping nếu thiếu base url
    import aiohttp
    url = f"{base}/health"
    while True:
        try:
            async with aiohttp.ClientSession() as sess:
                await sess.get(url, timeout=8)
        except Exception:
            pass
        await asyncio.sleep(240)  # 4 phút

# ---------- Đăng ký webhook với Telegram ----------
async def _ensure_webhook(app: Application):
    base = os.getenv("WEBHOOK_BASE_URL", "").rstrip("/")
    if not base:
        return
    path = f"/tg/{TELEGRAM_BOT_TOKEN}"
    url = base + path
    try:
        await app.bot.set_webhook(url=url, allowed_updates=["message", "edited_message", "callback_query"])
    except Exception:
        # Không lỗi hoá: nếu fail thì bạn vẫn có thể chuyển sang polling tạm thời (nếu muốn).
        pass

# ---------- FastAPI lifecycle ----------
@app.on_event("startup")
async def on_startup():
    """
    Khởi tạo PTB Application + set webhook + tự ping.
    """
    global _application, _self_ping_task

    # 1) build PTB application (handlers, jobs…)
    _application = build_telegram_application()

    # 2) init + start => JobQueue hoạt động, handlers sẵn sàng
    await _application.initialize()
    await _application.start()

    # 3) set webhook
    await _ensure_webhook(_application)

    # 4) self-ping task (chỉ chạy khi có WEBHOOK_BASE_URL)
    loop = asyncio.get_running_loop()
    _self_ping_task = loop.create_task(_self_ping_loop())

@app.on_event("shutdown")
async def on_shutdown():
    global _application, _self_ping_task
    try:
        if _self_ping_task:
            _self_ping_task.cancel()
    except Exception:
        pass
    if _application:
        try:
            await _application.stop()
        except Exception:
            pass
        try:
            await _application.shutdown()
        except Exception:
            pass

# ---------- Local run (tuỳ chọn) ----------
if __name__ == "__main__":
    port = int(os.getenv("PORT", "10000"))
    uvicorn.run("web:app", host="0.0.0.0", port=port, reload=False)
