# web.py — FastAPI webhook cho Render
# Start Command: uvicorn web:app --host 0.0.0.0 --port $PORT

import asyncio
from contextlib import asynccontextmanager
from urllib.parse import urlparse

import aiohttp
import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from telegram import Update
from telegram.error import TelegramError

from settings import PUBLIC_URL, SELF_URL, WEBHOOK_SECRET
from bots.telegram_bot.telegram_bot import build_app, send_signals

_app = None
_scheduler_task: asyncio.Task | None = None
_keep_awake_task: asyncio.Task | None = None


# ------------------------- Keep Awake (optional) -------------------------
async def keep_awake():
    """Ping SELF_URL mỗi 5 phút để Render không ngủ (nếu cấu hình)."""
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
    if not PUBLIC_URL or not WEBHOOK_SECRET:
        print("[WEBHOOK] Thiếu PUBLIC_URL/WEBHOOK_SECRET, bỏ qua.")
        return
    url = f"{PUBLIC_URL.rstrip('/')}/webhook/{WEBHOOK_SECRET}"
    try:
        await asyncio.wait_for(
            _app.bot.set_webhook(
                url=url, drop_pending_updates=True, secret_token=WEBHOOK_SECRET
            ),
            timeout=10,
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

# ---------------------- RELAY ONUS (desktop headers + debug) ----------------------
ONUS_UPSTREAMS = [
    "https://goonus.io/api/v1/futures/market-overview",
    "https://api-gateway.onus.io/futures/api/v1/market/overview",
    "https://api.onus.io/futures/api/v1/market/overview",
]


def build_pc_headers(u: str) -> dict:
    """Giả lập Windows + Chrome; header bám theo host của từng endpoint."""
    host = urlparse(u).hostname or "goonus.io"
    origin = f"https://{host}"
    referer = "https://goonus.io/future" if host == "goonus.io" else origin
    return {
        "Host": host,
        "Connection": "keep-alive",
        "sec-ch-ua": '"Not/A)Brand";v="99", "Google Chrome";v="124", "Chromium";v="124"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "Upgrade-Insecure-Requests": "1",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
        "Referer": referer,
        "Origin": origin,
        "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
        "Pragma": "no-cache",
        "Cache-Control": "no-cache",
    }


@app.get("/relay/onus")
async def relay_onus():
    """
    Proxy ONUS (header PC). Không văng 500: luôn trả JSON kết quả hoặc JSON debug `trials`.
    """
    import traceback

    trials = []  # thu thập thông tin từng upstream để chẩn đoán

    try:
        async with httpx.AsyncClient(timeout=12, follow_redirects=True, http2=True) as client:
            for u in ONUS_UPSTREAMS:
                try:
                    r = await client.get(u, headers=build_pc_headers(u))
                    trials.append({
                        "url": u,
                        "status": r.status_code,
                        "preview": (r.text or "")[:200],
                    })
                    if r.status_code == 200:
                        try:
                            data = r.json()
                        except Exception as je:
                            trials.append({"url": u, "json_error": str(je)})
                            continue
                        arr = data if isinstance(data, list) else data.get("data", data)
                        if isinstance(arr, list):
                            return JSONResponse(arr, media_type="application/json")
                        return JSONResponse(data, media_type="application/json")
                except Exception as e:
                    trials.append({"url": u, "exception": str(e)})
                    continue

    except Exception as e:
        tb = traceback.format_exc()
        print("[RELAY_FATAL]", tb)
        return JSONResponse(
            {"ok": False, "error": "relay fatal", "detail": str(e), "trace": tb},
            status_code=500,
        )

    # Không upstream nào thành công → trả debug để biết nguyên nhân
    return JSONResponse(
        {"ok": False, "error": "ONUS upstream unreachable", "trials": trials},
        status_code=502,
    )


# ------------------------------- Routes khác -------------------------------
@app.get("/")
async def root():
    return {"status": "ok"}


@app.post("/webhook/{secret}")
async def tg_webhook(secret: str, request: Request):
    header = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if secret != WEBHOOK_SECRET or header != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Invalid secret")
    data = await request.json()
    update = Update.de_json(data, _app.bot)
    await _app.process_update(update)
    return {"ok": True}
