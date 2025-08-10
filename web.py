# web.py — FastAPI webhook cho Render
# Start Command: uvicorn web:app --host 0.0.0.0 --port $PORT

import os
import asyncio
import aiohttp
import httpx
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from telegram import Update
from telegram.error import TelegramError

from settings import PUBLIC_URL, WEBHOOK_SECRET, SELF_URL
from bots.telegram_bot.telegram_bot import build_app, send_signals

_app = None
_scheduler_task = None
_keep_awake_task = None

# (tuỳ chọn) tự ping để Render không ngủ
async def keep_awake():
    url = (SELF_URL or "").rstrip("/")
    if not url:
        return
    async with aiohttp.ClientSession() as s:
        while True:
            try:
                async with s.get(url) as r:
                    print(f"[KEEP_AWAKE] {url} -> {r.status}")
            except Exception as e:
                print(f"[KEEP_AWAKE] error: {e}")
            await asyncio.sleep(300)

async def set_webhook_bg():
    """Đặt webhook ở background để không chặn health check."""
    global _app
    if not PUBLIC_URL or not WEBHOOK_SECRET:
        print("[WEBHOOK] Thiếu PUBLIC_URL/WEBHOOK_SECRET, bỏ qua.")
        return
    url = f"{PUBLIC_URL.rstrip('/')}/webhook/{WEBHOOK_SECRET}"
    try:
        await asyncio.wait_for(
            _app.bot.set_webhook(url=url, drop_pending_updates=True, secret_token=WEBHOOK_SECRET),
            timeout=10
        )
        print(f"[WEBHOOK] set to: {url}")
    except (asyncio.TimeoutError, TelegramError, Exception) as e:
        print(f"[WEBHOOK] set failed: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _app, _scheduler_task, _keep_awake_task
    _app = build_app()
    await _app.initialize()
    await _app.start()

    # scheduler placeholder (ổn, không gửi gì nếu bạn chưa bật)
    _scheduler_task = asyncio.create_task(send_signals(_app))
    _keep_awake_task = asyncio.create_task(keep_awake())
    asyncio.create_task(set_webhook_bg())

    print("[STARTUP] FastAPI ready (webhook mode)")
    try:
        yield
    finally:
        for t in (_scheduler_task, _keep_awake_task):
            if t and not t.done():
                t.cancel()
                try:
                    await t
                except asyncio.CancelledError:
                    pass
        if _app:
            await _app.stop()
            await _app.shutdown()
        print("[SHUTDOWN] stopped")

app = FastAPI(lifespan=lifespan)

# ----------------- RELAY ONUS (Render làm proxy) -----------------
PC_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://goonus.io/future",
    "Origin": "https://goonus.io",
    "Connection": "keep-alive",
    "Pragma": "no-cache",
    "Cache-Control": "no-cache",
}
ONUS_UPSTREAMS = [
    "https://goonus.io/api/v1/futures/market-overview",
    "https://api-gateway.onus.io/futures/api/v1/market/overview",
    "https://api.onus.io/futures/api/v1/market/overview",
]

@app.get("/relay/onus")
async def relay_onus():
    """Proxy qua Render để lấy dữ liệu ONUS (trả JSON mảng)."""
    async with httpx.AsyncClient(timeout=8, headers=PC_HEADERS, follow_redirects=True) as client:
        for u in ONUS_UPSTREAMS:
            try:
                r = await client.get(u)
                if r.status_code == 200:
                    try:
                        data = r.json()
                    except Exception:
                        continue
                    # Chuẩn hoá: nếu {data:[...]} → trả mảng; nếu là mảng → giữ nguyên
                    arr = data if isinstance(data, list) else data.get("data", data)
                    if isinstance(arr, list):
                        return JSONResponse(arr, media_type="application/json")
                    return JSONResponse(data, media_type="application/json")
            except Exception:
                pass
    return JSONResponse({"ok": False, "error": "ONUS upstream unreachable"}, status_code=502)
# -----------------------------------------------------------------

@app.get("/")
async def root():
    return {"status": "ok"}

@app.post("/webhook/{secret}")
async def tg_webhook(secret: str, request: Request):
    if secret != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Invalid webhook secret")
    header = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if header != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Invalid secret token header")

    data = await request.json()
    update = Update.de_json(data, _app.bot)
    await _app.process_update(update)
    return {"ok": True}
