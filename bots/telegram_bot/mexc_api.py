# -*- coding: utf-8 -*-
"""
MEXC API (đã gắn ONUS price format)
- Đọc KEY/SECRET từ env hoặc settings
- Lấy tickers futures, kline ngắn hạn
- market_snapshot(): snapshot nhanh cho status/health
- smart_pick_signals(): tạo tín hiệu scalping (market/limit) demo
"""

from __future__ import annotations
import os, time, hmac, hashlib
from typing import List, Dict, Tuple
import requests

# ----- settings -----
try:
    from settings import MEXC_API_KEY, MEXC_API_SECRET, USDVND_URL
except Exception:
    MEXC_API_KEY = os.getenv("MEXC_API_KEY", "")
    MEXC_API_SECRET = os.getenv("MEXC_API_SECRET", "")
    USDVND_URL = os.getenv("USDVND_URL", "https://open.er-api.com/v6/latest/USD")

# public futures endpoints (ổn định)
CONTRACT_BASE = "https://contract.mexc.com"
TICKER_URL    = f"{CONTRACT_BASE}/api/v1/contract/ticker"          # ?symbol= or all
KLINE_URL     = f"{CONTRACT_BASE}/api/v1/contract/kline"           # ?symbol=&interval=Min1&limit=60

HTTP_TIMEOUT = 8
UA = {"User-Agent": "autiner/1.0"}

# ----- price format (đã sẵn có) -----
from ..pricing.onus_format import display_price  # (name, price_str) = display_price(symbol, last_usd, vnd, unit)

def _jget(url: str, params: Dict | None = None) -> Dict | List | None:
    try:
        r = requests.get(url, params=params or {}, headers=UA, timeout=HTTP_TIMEOUT)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None

def usd_vnd_rate() -> float:
    try:
        js = _jget(USDVND_URL)
        return float(js.get("rates", {}).get("VND", 0.0)) if isinstance(js, dict) else 0.0
    except Exception:
        return 0.0

# ======================================================================
# Public market fetchers
# ======================================================================
def fetch_all_tickers() -> List[Dict]:
    """
    Trả về list tickers chuẩn hoá:
    [{symbol:'BTC_USDT', last:float, qv:float, chg:float}, ...]
    """
    js = _jget(TICKER_URL)
    rows = []
    if isinstance(js, dict) and js.get("success"):
        rows = js.get("data") or []
    elif isinstance(js, list):
        rows = js
    out = []
    for it in rows:
        sym = it.get("symbol")
        if not sym or not str(sym).endswith("_USDT"):  # futures ký hiệu như BTC_USDT
            continue
        try:
            last = float(it.get("lastPrice", it.get("last", 0.0)))
        except: last = 0.0
        try:
            qv = float(it.get("volumeQuote", it.get("quoteVol", 0.0)))
        except: qv = 0.0
        try:
            chg = float(it.get("riseFallRate", it.get("changeRate", 0.0)))
            if abs(chg) < 1.0: chg *= 100.0
        except: chg = 0.0
        out.append({"symbol": sym, "last": last, "qv": qv, "chg": chg})
    return out

def fetch_klines(symbol: str, limit: int = 60) -> List[Dict]:
    """
    Kline 1m cho phân tích đơn giản:
    mỗi item: {t, o, h, l, c, v}
    """
    params = {"symbol": symbol, "interval": "Min1", "limit": max(10, min(200, limit))}
    js = _jget(KLINE_URL, params=params)
    data = []
    if isinstance(js, dict) and js.get("success"):
        for k in js.get("data", []):
            # API trả: [ts, open, high, low, close, vol, ...]
            try:
                data.append({
                    "t": int(k[0]), "o": float(k[1]), "h": float(k[2]),
                    "l": float(k[3]), "c": float(k[4]), "v": float(k[5])
                })
            except Exception:
                continue
    return data

# ======================================================================
# Health + snapshot + signal builder
# ======================================================================
def market_snapshot(unit: str = "USD", topn: int = 5) -> Tuple[List[Dict], bool, float]:
    """
    Trả: (coins, live, rate)
    coins: [{symbol, last_usd, price_str, chg, qv}]
    """
    vnd = usd_vnd_rate()
    ticks = fetch_all_tickers()
    live = bool(ticks)
    if not live:
        return [], False, vnd
    # sort theo volume
    ticks.sort(key=lambda d: d.get("qv", 0.0), reverse=True)
    pool = ticks[:max(1, topn)]
    out = []
    for d in pool:
        name, pstr = display_price(d["symbol"], d["last"], vnd, unit=unit)
        out.append({
            "symbol": d["symbol"], "display": name,
            "last_usd": d["last"], "price_str": pstr, "chg": float(d["chg"]), "qv": float(d["qv"])
        })
    return out, True, vnd

def _side_from_momentum(kl: List[Dict]) -> str:
    """Đơn giản: close > SMA(20) → LONG, ngược lại SHORT."""
    if len(kl) < 20: return "LONG"
    sma = sum(k["c"] for k in kl[-20:]) / 20.0
    return "LONG" if kl[-1]["c"] >= sma else "SHORT"

def smart_pick_signals(unit: str, n: int = 3) -> Tuple[List[Dict], Dict, bool, float]:
    """
    Tạo n tín hiệu scalping (demo nhưng mượt & không block).
    Trả: (signals, highlights, live, vnd_rate)
    signal:
      {token, unit, side, orderType, entry, tp, sl, strength, reason}
    """
    coins, live, vnd = market_snapshot(unit=unit, topn=max(10, n*4))
    if not live or not coins:
        return None, None, False, vnd

    # chọn những mã biến động + volume nhất
    pool = sorted(coins, key=lambda x: (abs(x["chg"]), x["qv"]), reverse=True)[:n*2]
    out = []
    for d in pool[:n]:
        sym  = d["symbol"]
        kl   = fetch_klines(sym, limit=60)
        side = _side_from_momentum(kl)
        last = kl[-1]["c"] if kl else d["last_usd"]

        # build entry/tp/sl (ATR thô từ 14 nến)
        if kl and len(kl) >= 15:
            tr = [max(kl[i]["h"]-kl[i]["l"], abs(kl[i]["h"]-kl[i-1]["c"]), abs(kl[i]["l"]-kl[i-1]["c"])) for i in range(1,15)]
            atr = sum(tr)/len(tr)
        else:
            atr = last * 0.003  # fallback 0.3%

        if side == "LONG":
            entry = last
            tp    = last + 2.0*atr
            sl    = last - 1.5*atr
        else:
            entry = last
            tp    = last - 2.0*atr
            sl    = last + 1.5*atr

        # định dạng hiển thị theo ONUS (đúng cho cả coin nhỏ/lớn)
        name, entry_str = display_price(sym, entry, vnd, unit)
        _, tp_str  = display_price(sym, tp, vnd, unit)
        _, sl_str  = display_price(sym, sl, vnd, unit)

        out.append({
            "token": name, "unit": unit, "side": side,
            "orderType": "MARKET",  # demo: MARKET; có thể thêm LIMIT tuỳ spread
            "entry": entry_str, "tp": tp_str, "sl": sl_str,
            "strength": 70 if abs(d["chg"]) < 1.5 else 78 if abs(d["chg"]) < 3 else 82,
            "reason": "SMA20 momentum; ATR x2 TP, x1.5 SL; top vol 24h"
        })

    highlights = {"note": "Top biến động theo vol & momentum 1m"}
    return out, highlights, True, vnd
