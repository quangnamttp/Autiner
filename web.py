# -*- coding: utf-8 -*-
import os
from fastapi import FastAPI

app = FastAPI(title="Autiner Web")

@app.get("/")
def root():
    return {"ok": True, "service": "autiner-web"}

@app.get("/healthz")
def healthz():
    # báo trạng thái một số ENV (mask secret)
    mexc_key = os.getenv("MEXC_API_KEY", "")
    key_mask = (mexc_key[:4] + "..." + mexc_key[-3:]) if len(mexc_key) >= 8 else ("set" if mexc_key else "unset")
    return {
        "status": "ok",
        "tz": os.getenv("TZ_NAME", "Asia/Ho_Chi_Minh"),
        "unit": os.getenv("DEFAULT_UNIT", "VND"),
        "telegram": "set" if os.getenv("TELEGRAM_BOT_TOKEN") else "unset",
        "mexc_api_key": key_mask,
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("web:app", host="0.0.0.0", port=port, reload=False)
