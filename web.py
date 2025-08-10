# web.py — Start Command: uvicorn web:app --host 0.0.0.0 --port $PORT
import os, threading, asyncio, aiohttp
from fastapi import FastAPI
from bots.telegram_bot import build_app

app = FastAPI()
_app = None
_poll_thread = None

async def keep_awake():
    url = os.getenv("SELF_URL")
    if not url: return
    async with aiohttp.ClientSession() as s:
        while True:
            try:
                async with s.get(url) as r:
                    print(f"[KEEP_AWAKE] {url} -> {r.status}")
            except Exception as e:
                print(f"[KEEP_AWAKE] error: {e}")
            await asyncio.sleep(300)

def _polling_thread():
    global _app
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    async def runner():
        await _app.run_polling(close_loop=False)
    loop.run_until_complete(runner())
    loop.close()

@app.on_event("startup")
async def startup():
    global _app, _poll_thread
    _app = build_app()
    # QUAN TRỌNG: xóa webhook để polling nhận update
    await _app.bot.delete_webhook(drop_pending_updates=True)
    _poll_thread = threading.Thread(target=_polling_thread, daemon=True)
    _poll_thread.start()
    asyncio.create_task(keep_awake())
    print("[STARTUP] polling started")

@app.on_event("shutdown")
async def shutdown():
    global _app
    if _app:
        await _app.stop(); await _app.shutdown()
    print("[SHUTDOWN] stopped")

@app.get("/")
async def root():
    return {"status": "ok"}
