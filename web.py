# web.py
# -*- coding: utf-8 -*-
"""
Webhook server (FastAPI) cho Telegram bot + tự ping keep-alive cho Render.

• Endpoint:
  - GET/HEAD  /          -> "OK" (health)
  - GET/HEAD  /health    -> "OK" (health)
  - POST      /tg/<TOKEN>-> Webhook Telegram (TOKEN lấy từ env TELEGRAM_BOT_TOKEN)

ENV cần:
  TELEGRAM_BOT_TOKEN (bắt buộc)
  WEBHOOK_BASE_URL   (ví dụ: https://autiner.onrender.com)
  SELF_PING_INTERVAL_SEC (tùy chọn, mặc định 300 = 5 phút)
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

# dùng cấu trúc repo: bots/...
from bots.telegram_bot.telegram_bot import build_app as build_telegram_application

# ---------- FastAPI ----------
app = FastAPI(title="Autiner Webhook")

# Globals
_application: Optional[Application] = None
_self_ping_task: Optional[asyncio.Task] = None

# ---------- Health endpoints (GET + HEAD để Render health-check không 405) ----------
@app.api_route("/", methods=["GET", "HEAD"], response_class=PlainTextResponse)
@app.api_route("/health", methods=["GET", "HEAD"], response_class=PlainTextResponse)
async def health() -> str:
    return "OK"

# ---------- Telegram webhook ----------
@app.post(f"/tg/{TELEGRAM_BOT_TOKEN}")
async def telegram_webhook(req: Request) -> Response:
    global _application
    if _application is None:
        return Response(status_code=503)  # chưa sẵn sàng
    try:
        data = await req.json()
        update = Update.de_json(data=data, bot=_application.bot)
        # đẩy vào hàng đợi để PTB xử lý (không block FastAPI)
        await _application.update_queue.put(update)
    except Exception:
        return Response(status_code=400)  # payload không hợp lệ
    return Response(status_code=200)

# ---------- Tự ping giữ dịch vụ không ngủ (mặc định 5 phút) ----------
async def _self_ping_loop():
    base = os.getenv("WEBHOOK_BASE_URL", "").rstrip("/")
    if not base:
        return  # không tự ping nếu thiếu base url

    # Cho phép cấu hình khoảng ping, mặc định 300s (5 phút)
    try:
        interval = int(os.getenv("SELF_PING_INTERVAL_SEC", "300"))
    except Exception:
        interval = 300

    # Đường dẫn ping — dùng /health cho nhẹ & rẻ
    url = f"{base}/health"

    import aiohttp
    # Dùng một ClientSession tái sử dụng để tiết kiệm kết nối
    async with aiohttp.ClientSession() as sess:
        while True:
            try:
                # dùng HEAD trước, nếu server/proxy không hỗ trợ thì fallback GET
                async with sess.head(url, timeout=8) as _:
                    pass
            except Exception:
                try:
                    async with sess.get(url, timeout=8) as _:
                        pass
                except Exception:
                    # nuốt lỗi — chỉ là keep-alive
                    pass
            await asyncio.sleep(max(60, interval))  # tối thiểu 60s phòng cấu hình sai

# ---------- Đăng ký webhook với Telegram ----------
async def _ensure_webhook(app_ptb: Application):
    base = os.getenv("WEBHOOK_BASE_URL", "").rstrip("/")
    if not base or not TELEGRAM_BOT_TOKEN:
        return
    path = f"/tg/{TELEGRAM_BOT_TOKEN}"
    url = base + path
    try:
        await app_ptb.bot.set_webhook(
            url=url,
            allowed_updates=["message", "edited_message", "callback_query"]
        )
    except Exception:
        # Không raise: nếu fail bạn vẫn có thể chuyển hướng sang polling tạm
        pass

# ---------- FastAPI lifecycle ----------
@app.on_event("startup")
async def on_startup():
    """
    Khởi tạo PTB Application + set webhook + self-ping.
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
