# autiner_bot/data_sources/binance.py
import requests
import asyncio
import time
import numpy as np
import traceback

BINANCE_FUTURES_URL = "https://fapi.binance.com"
BINANCE_P2P_URL = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"

HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (AutinerBot; +binance-futures)",
    "Accept": "application/json",
}

P2P_HEADERS = {
    "Content-Type": "application/json",
    "Origin": "https://p2p.binance.com",
    "Referer": "https://p2p.binance.com/",
    "User-Agent": "Mozilla/5.0 (AutinerBot; +binance-p2p)"
}

# ---------- helpers (sync) ----------
def _get_json_sync(url: str, timeout=20):
    r = requests.get(url, headers=HTTP_HEADERS, timeout=timeout)
    r.raise_for_status()
    return r.json()

def _post_json_sync(url: str, payload: dict, timeout=20, headers=None):
    r = requests.post(url, json=payload, headers=headers or HTTP_HEADERS, timeout=timeout)
    r.raise_for_status()
    return r.json()

# ---------- cache ----------
_ALL_TICKERS_CACHE = {"ts": 0, "data": []}

# =============================
# 24h tickers (Futures)
# =============================
async def get_all_futures(ttl=10):
    try:
        now = int(time.time())
        if now - _ALL_TICKERS_CACHE["ts"] <= ttl and _ALL_TICKERS_CACHE["data"]:
            return _ALL_TICKERS_CACHE["data"]

        url = f"{BINANCE_FUTURES_URL}/fapi/v1/ticker/24hr"
        data = await asyncio.to_thread(_get_json_sync, url, 25)  # chạy sync trong thread
        if isinstance(data, list) and data:
            _ALL_TICKERS_CACHE["ts"] = now
            _ALL_TICKERS_CACHE["data"] = data
            return data
        return []
    except Exception as e:
        print(f"[ERROR] get_all_futures: {e}")
        print(traceback.format_exc())
        return []

# =============================
# Kline (Futures)
# =============================
async def get_kline(symbol: str, interval="15m", limit=250):
    try:
        symbol = symbol.upper()
        url = f"{BINANCE_FUTURES_URL}/fapi/v1/klines?symbol={symbol}&interval={interval}&limit={limit}"
        data = await asyncio.to_thread(_get_json_sync, url, 25)
        return data if isinstance(data, list) else []
    except Exception as e:
        print(f"[ERROR] get_kline({symbol}): {e}")
        print(traceback.format_exc())
        return []

# =============================
# P2P USDT/VND (dùng requests luôn)
# =============================
async def get_usdt_vnd_rate() -> float:
    payload = {
        "asset": "USDT",
        "fiat": "VND",
        "merchantCheck": False,
        "page": 1,
        "rows": 10,
        "tradeType": "SELL",
        "payTypes": [],
        "publisherType": None
    }
    try:
        data = await asyncio.to_thread(_post_json_sync, BINANCE_P2P_URL, payload, 20, P2P_HEADERS)
        advs = data.get("data", [])
        prices = []
        for item in advs[:5]:
            adv = item.get("adv") or {}
            p = adv.get("price")
            if p is not None:
                try:
                    prices.append(float(p))
                except:
                    pass
        return float(sum(prices) / len(prices)) if prices else 0.0
    except Exception as e:
        print(f"[ERROR] get_usdt_vnd_rate: {e}")
        print(traceback.format_exc())
        return 0.0

# =============================
# (GIỮ nguyên calculate_indicators() & analyze_coin() của bạn)
# =============================

# ===== Diagnose (để test nhanh trên server) =====
async def diagnose_binance():
    info = {"ping": None, "tickers_status": None, "tickers_len": None, "sample": None, "error": None}
    try:
        # ping
        try:
            r1 = requests.get(f"{BINANCE_FUTURES_URL}/fapi/v1/ping", headers=HTTP_HEADERS, timeout=10)
            info["ping"] = r1.status_code
        except Exception as e:
            info["error"] = f"ping_error: {e}"

        # tickers
        try:
            r2 = requests.get(f"{BINANCE_FUTURES_URL}/fapi/v1/ticker/24hr", headers=HTTP_HEADERS, timeout=15)
            info["tickers_status"] = r2.status_code
            if r2.status_code == 200:
                js = r2.json()
                info["tickers_len"] = len(js) if isinstance(js, list) else None
                info["sample"] = js[0] if isinstance(js, list) and js else None
            else:
                info["error"] = r2.text[:300]
        except Exception as e:
            info["error"] = f"tickers_error: {e}"
    except Exception as e:
        info["error"] = f"{e}"
    return info
