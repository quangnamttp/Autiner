# -*- coding: utf-8 -*-
"""
MEXC Futures Client (HTTP bền vững + health ping)
- fetch_tickers()      -> list chuẩn hoá (symbol,last,qv,chg)
- fetch_funding()      -> {symbol: funding_percent}
- fetch_klines_1m(sym) -> list OHLCV 1m (120 nến)
- get_usd_vnd_rate()   -> tỷ giá
- health_ping()        -> ping nhẹ Render + MEXC (giữ bot không "ngủ")
"""

from __future__ import annotations
import os, time, hmac, hashlib
from typing import List, Dict
import requests

from settings import (
    MEXC_TICKER_URL, MEXC_FUNDING_URL, MEXC_KLINES_URL,
    USDVND_URL, HTTP_TIMEOUT, HTTP_RETRY
)

API_KEY    = os.getenv("MEXC_API_KEY")    # đặt env hoặc trong settings của bạn
API_SECRET = os.getenv("MEXC_API_SECRET")

_session = requests.Session()
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124 Safari/537.36",
    "Accept": "application/json",
}
if API_KEY:
    _HEADERS["ApiKey"] = API_KEY  # một số endpoint private cần header này

def _get_json(url: str, params: Dict | None = None, signed: bool = False):
    """
    Getter chung có retry/backoff.
    signed=True để minh hoạ (market data không cần ký).
    """
    for attempt in range(max(1, HTTP_RETRY)):
        try:
            if signed and API_KEY and API_SECRET:
                # NOTE: Market data của MEXC là public; phần ký chỉ để mở rộng sau này (account, order)
                params = params or {}
                params["timestamp"] = int(time.time() * 1000)
                qs = "&".join([f"{k}={params[k]}" for k in sorted(params)])
                sig = hmac.new(API_SECRET.encode(), qs.encode(), hashlib.sha256).hexdigest()
                params["signature"] = sig

            r = _session.get(url, params=params, headers=_HEADERS, timeout=HTTP_TIMEOUT)
            if r.status_code == 200:
                return r.json()
            time.sleep(0.2 * (attempt + 1))
        except Exception:
            time.sleep(0.2 * (attempt + 1))
    return None

def get_usd_vnd_rate() -> float:
    js = _get_json(USDVND_URL)
    try:
        return float(js.get("rates", {}).get("VND", 0.0)) if isinstance(js, dict) else 0.0
    except Exception:
        return 0.0

def fetch_tickers() -> List[Dict]:
    js = _get_json(MEXC_TICKER_URL)
    out = []
    rows = []
    if isinstance(js, dict) and (js.get("success") or "data" in js):
        rows = js.get("data") or []
    elif isinstance(js, list):
        rows = js

    for it in rows:
        sym = it.get("symbol") or it.get("instrument_id")
        if not sym or not str(sym).endswith("_USDT"):
            continue
        # last
        try:
            last = float(it.get("lastPrice") or it.get("last") or it.get("price") or it.get("close") or 0.0)
        except:
            last = 0.0
        # quoteVol 24h (USDT)
        try:
            qv = float(it.get("quoteVol") or it.get("amount24") or it.get("turnover") or it.get("turnover24") or 0.0)
        except:
            qv = 0.0
        # % change 24h
        try:
            raw = it.get("riseFallRate") or it.get("changeRate") or it.get("percent") or 0
            chg = float(raw)
            if abs(chg) < 1.0:
                chg *= 100.0
        except:
            chg = 0.0

        out.append({"symbol": str(sym), "last": last, "qv": qv, "chg": chg})
    return out

def fetch_funding() -> Dict[str, float]:
    js = _get_json(MEXC_FUNDING_URL)
    fmap: Dict[str, float] = {}
    if js is None:
        return fmap

    rows = None
    if isinstance(js, dict):
        if isinstance(js.get("data"), list):
            rows = js["data"]
        elif isinstance(js.get("list"), list):
            rows = js["list"]
        elif js.get("success") and isinstance(js.get("data"), list):
            rows = js["data"]
    elif isinstance(js, list):
        rows = js

    if not rows:
        return fmap

    for it in rows:
        try:
            s = it.get("symbol") or it.get("currency")
            if not s or not str(s).endswith("_USDT"):
                continue
            val = None
            for k in ("fundingRate", "rate", "value"):
                if isinstance(it, dict) and k in it:
                    val = it[k]; break
            fr = float(val) if val is not None else 0.0
            if abs(fr) < 1.0:
                fr = fr * 100.0
            fmap[str(s)] = fr
        except Exception:
            continue
    return fmap

def fetch_klines_1m(symbol: str, limit: int = 120) -> List[Dict]:
    url = MEXC_KLINES_URL.format(sym=symbol)
    js = _get_json(url)
    out = []
    rows = []
    if isinstance(js, dict) and "data" in js:
        rows = js.get("data") or []
    elif isinstance(js, list):
        rows = js

    for r in rows:
        try:
            # [time_ms, open, high, low, close, vol, ...]
            t = int(r[0]) // 1000
            o = float(r[1]); h = float(r[2]); l = float(r[3]); c = float(r[4]); v = float(r[5])
            out.append({"t": t, "o": o, "h": h, "l": l, "c": c, "v": v})
        except Exception:
            try:
                t = int(r.get("time", 0)) // 1000
                o = float(r.get("open")); h = float(r.get("high")); l = float(r.get("low")); c = float(r.get("close")); v = float(r.get("vol"))
                out.append({"t": t, "o": o, "h": h, "l": l, "c": c, "v": v})
            except Exception:
                pass
    out.sort(key=lambda x: x["t"])
    return out[-min(limit, 120):]

def health_ping() -> bool:
    """
    Ping nhanh để:
      - giữ Render awake (bằng 1 call mạng thật)
      - xác nhận public API hoạt động
    Trả True/False (không raise).
    """
    try:
        _ = fetch_tickers()
        _ = get_usd_vnd_rate()
        return True
    except Exception:
        return False
