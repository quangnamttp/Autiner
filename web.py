# autiner/web.py
import asyncio
import os
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return {"ok": True, "bot": "autiner", "status": "running"}

async def _self_ping():
    """Tự ping để tránh Render sleep."""
    import httpx
    url = os.getenv("SELF_URL")
    if not url:
        return
    while True:
        try:
            async with httpx.AsyncClient(timeout=10) as cli:
                await cli.get(url)
        except Exception:
            pass
        await asyncio.sleep(14 * 60)

@app.on_event("startup")
async def on_start():
    asyncio.create_task(_self_ping())
