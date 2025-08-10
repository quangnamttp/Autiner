# web.py — FastAPI webhook cho Render + relay ONUS qua trình duyệt PC
# Start Command: uvicorn web:app --host 0.0.0.0 --port $PORT

import os
import asyncio
import aiohttp
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from telegram import Update
from telegram.error import TelegramError
from playwright.async_api import async_playwright

from settings import PUBLIC_URL, WEBHOOK_SECRET, SELF_URL
from bots.telegram_bot.telegram_bot import build_app, send_signals

_app = None
_scheduler_task = None
_keep_awake_task = None

# --- Hàm giả lập PC truy cập ONUS ---
async def fetch_onus_browser():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = await browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/124.0.0.0 Safari/537.36"
        )
        await page.goto("https://goonus.io/future", timeout=20000)
        await page.wait_for_timeout(5000)  # đợi trang và API load

        # Lấy dữ liệu từ biến JS của trang
        data = await page.evaluate("""
            () => {
                return window.__NEXT_DATA__?.props?.pageProps?.initialData || null;
            }
        """)

        await browser.close()
        return data

# --- Tự ping để Render không ngủ ---
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

# --- Đặt webhook cho Telegram ---
async def set_webhook_bg():
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

# --- Khởi tạo FastAPI ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _app, _scheduler_task, _keep_awake_task
    _app = build_app()
    await _app.initialize()
    await _app.start()

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

# --- API Relay ONUS ---
@app.get("/relay/onus")
async def relay_onus():
    try:
        data = await fetch_onus_browser()
        if isinstance(data, dict) and "data" in data:
            return JSONResponse(data["data"], media_type="application/json")
        elif isinstance(data, list):
            return JSONResponse(data, media_type="application/json")
        else:
            return JSONResponse({"ok": False, "error": "No valid data"}, status_code=500)
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

# --- Root Check ---
@app.get("/")
async def root():
    return {"status": "ok"}

# --- Telegram Webhook ---
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
