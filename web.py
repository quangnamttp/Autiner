# web.py — FastAPI webhook cho Render
# Start Command: uvicorn web:app --host 0.0.0.0 --port $PORT
import asyncio
from contextlib import asynccontextmanager
import aiohttp
from fastapi import FastAPI, Request, HTTPException
from telegram import Update
from telegram.error import TelegramError

from settings import PUBLIC_URL, WEBHOOK_SECRET, SELF_URL
from bots.telegram_bot.telegram_bot import build_app

_app = None
_keep_awake_task: asyncio.Task | None = None

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
    global _app
    if not PUBLIC_URL or not WEBHOOK_SECRET:
        print("[WEBHOOK] Thiếu PUBLIC_URL/WEBHOOK_SECRET.")
        return
    url = f"{PUBLIC_URL.rstrip('/')}/webhook/{WEBHOOK_SECRET}"
    try:
        await asyncio.wait_for(
            _app.bot.set_webhook(url=url, drop_pending_updates=True, secret_token=WEBHOOK_SECRET),
            timeout=10
        )
        print(f"[WEBHOOK] set → {url}")
    except (asyncio.TimeoutError, TelegramError, Exception) as e:
        print(f"[WEBHOOK] set failed: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _app, _keep_awake_task
    _app = build_app()
    await _app.initialize()
    await _app.start()

    _keep_awake_task = asyncio.create_task(keep_awake())
    asyncio.create_task(set_webhook_bg())

    print("[STARTUP] webhook mode ready")
    try:
        yield
    finally:
        if _keep_awake_task and not _keep_awake_task.done():
            _keep_awake_task.cancel()
            try:
                await _keep_awake_task
            except asyncio.CancelledError:
                pass
        if _app:
            await _app.stop()
            await _app.shutdown()
        print("[SHUTDOWN] stopped")

app = FastAPI(lifespan=lifespan)

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
