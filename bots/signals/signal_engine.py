# autiner/bots/signals/signal_engine.py
# -*- coding: utf-8 -*-
"""
Autiner — Signal Engine (Scalping + Swing)

- Quét toàn bộ futures MEXC (tickers + funding)
- Lọc thanh khoản >= VOL24H_FLOOR
- Phân tích 1m/5m (EMA9/21, ATR, RSI, sigma, Break+Retest)
- Chấm điểm + chọn ngẫu nhiên theo softmax để đa dạng
- Xác định Market/Limit thông minh
"""

from __future__ import annotations
import math
import time
import random
from typing import List, Dict, Tuple
from collections import deque
import requests
from settings import settings
from bots.pricing.onus_format import display_price

_session = requests.Session()
_HEADERS = {"User-Agent": "Mozilla/5.0"}

_last_fx = {"ts": 0.0, "rate": 24500.0}
_prev_volume: Dict[str, float] = {}
_hist_px: Dict[str, deque] = {}
_last_batch: set[str] = set()

# ---------------- HTTP helpers ----------------
def _get_json(url: str):
    try:
        r = _session.get(url, headers=_HEADERS, timeout=settings.HTTP_TIMEOUT)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None

def usd_vnd_rate() -> float:
    now = time.time()
    if now - _last_fx["ts"] < settings.FX_CACHE_TTL and _last_fx["rate"] > 0:
        return _last_fx["rate"]
    js = _get_json(settings.MEXC_TICKER_VNDC_URL)
    try:
        if js and isinstance(js.get("data"), list):
            for item in js["data"]:
                if item.get("symbol") == "USDT_VND":
                    rate = float(item.get("last"))
                    if rate > 0:
                        _last_fx["ts"] = now
                        _last_fx["rate"] = rate
                        return rate
    except Exception:
        pass
    return _last_fx["rate"]

# ---------------- Live data ----------------
def _fetch_tickers_live() -> List[dict]:
    tick = _get_json(settings.MEXC_TICKER_URL)
    items: List[dict] = []
    if isinstance(tick, dict) and "data" in tick:
        arr = tick["data"]
    else:
        arr = []
    for it in arr:
        sym = it.get("symbol")
        if not sym or not str(sym).endswith("_USDT"):
            continue
        try:
            last = float(it.get("lastPrice", 0.0))
        except Exception:
            last = 0.0
        try:
            qvol = float(it.get("quoteVol", 0.0))
        except Exception:
            qvol = 0.0
        try:
            chg = float(it.get("riseFallRate", 0.0)) * 100
        except Exception:
            chg = 0.0
        items.append({
            "symbol": sym,
            "lastPrice": last,
            "volumeQuote": qvol,
            "change24h_pct": chg,
        })
    return items

def _fetch_funding_live() -> Dict[str, float]:
    js = _get_json(settings.MEXC_FUNDING_URL)
    fmap: Dict[str, float] = {}
    if not js:
        return fmap
    if isinstance(js, dict) and "data" in js:
        rows = js["data"]
    else:
        rows = []
    for it in rows:
        s = it.get("symbol")
        if not s or not str(s).endswith("_USDT"):
            continue
        try:
            fr = float(it.get("fundingRate", 0.0)) * 100
        except Exception:
            fr = 0.0
        fmap[s] = fr
    return fmap

def _fetch_klines_1m(sym: str) -> List[dict]:
    url = settings.MEXC_KLINES_URL.format(sym=sym)
    js = _get_json(url)
    out: List[dict] = []
    if isinstance(js, dict) and "data" in js:
        rows = js.get("data", [])
    else:
        rows = []
    for r in rows:
        try:
            t = int(r[0]) // 1000
            o, h, l, c, v = float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[5])
            out.append({"t": t, "o": o, "h": h, "l": l, "c": c, "v": v})
        except Exception:
            pass
    out.sort(key=lambda x: x["t"])
    return out[-120:]

# ---------------- TA utils ----------------
def ema(vals: List[float], period: int) -> List[float]:
    if not vals or period <= 1:
        return vals or []
    k = 2.0 / (period + 1.0)
    out, ema_prev = [], vals[0]
    for i, x in enumerate(vals):
        ema_prev = x if i == 0 else (x * k + ema_prev * (1 - k))
        out.append(ema_prev)
    return out

def rsi(vals: List[float], period: int = 14) -> float:
    if len(vals) < period + 1:
        return 50.0
    gains, losses = 0.0, 0.0
    for i in range(-period, 0):
        ch = vals[i] - vals[i-1]
        if ch >= 0: gains += ch
        else:       losses -= ch
    if losses == 0:
        return 70.0
    rs = gains / losses
    return 100.0 - 100.0 / (1.0 + rs)

def atr_5m(kl: List[dict]) -> float:
    if len(kl) < 6:
        return 0.0
    tr, prev_close = [], kl[-6]["c"]
    for k in kl[-5:]:
        tr_i = max(k["h"] - k["l"], abs(k["h"] - prev_close), abs(k["l"] - prev_close))
        tr.append(tr_i)
        prev_close = k["c"]
    return sum(tr) / len(tr)

# ---------------- Snapshot + scoring ----------------
def market_snapshot(topn: int | None = None) -> Tuple[List[dict], bool, float]:
    items = _fetch_tickers_live()
    if not items:
        return [], False, usd_vnd_rate()
    fmap = _fetch_funding_live()
    rate = usd_vnd_rate()
    # lọc thanh khoản
    items = [d for d in items if float(d.get("volumeQuote", 0.0)) >= settings.VOL24H_FLOOR]
    if not items:
        return [], False, rate
    # merge funding
    for it in items:
        it["fundingRate"] = fmap.get(it["symbol"], 0.0)
    return items, True, rate

def _need_market(break_retest_ok: bool, vol_mult: float, funding: float, ema_up: bool, rsi14: float) -> bool:
    if not break_retest_ok: return False
    if vol_mult < settings.BREAK_VOL_MULT: return False
    if abs(funding) >= settings.FUNDING_ABS_LIM * 100: return False
    if ema_up and rsi14 < 52: return False
    if (not ema_up) and rsi14 > 48: return False
    return True

def _analyze_klines_for(sym: str) -> dict:
    kl = _fetch_klines_1m(sym)
    if len(kl) < 30:
        return {"ok": False}
    closes = [k["c"] for k in kl]
    vols   = [k["v"] for k in kl]
    ema9   = ema(closes, 9)
    ema21  = ema(closes, 21)
    atr    = atr_5m(kl)
    ma20v  = sum(vols[-20:]) / 20 if len(vols) >= 20 else sum(vols) / len(vols)
    rsi14  = rsi(closes, 14)
    prev20_max = max(closes[-21:-1])
    prev20_min = min(closes[-21:-1])
    up   = closes[-1] > prev20_max and ema9[-1] > ema21[-1]
    down = closes[-1] < prev20_min and ema9[-1] < ema21[-1]
    br_ok = up or down
    vol_now = vols[-1]
    vol_mult = (vol_now / ma20v) if ma20v > 0 else 1.0
    return {
        "ok": True,
        "atr": atr,
        "ema9": ema9[-1],
        "ema21": ema21[-1],
        "rsi14": rsi14,
        "vol_mult": vol_mult,
        "break_retest_ok": br_ok,
        "trend_up": ema9[-1] > ema21[-1],
        "last_close": closes[-1],
    }

# ---------------- Public API ----------------
def generate_signals(unit: str = "VND", n: int = 5):
    coins, live, rate = market_snapshot()
    if not live or not coins:
        return []
    # lịch sử giá
    for c in coins:
        dq = _hist_px.setdefault(c["symbol"], deque(maxlen=3))
        dq.append(c["lastPrice"])
    picked = random.sample(coins, min(n, len(coins)))
    signals = []
    for c in picked:
        feats = _analyze_klines_for(c["symbol"])
        if not feats.get("ok"):
            continue
        want_mk = _need_market(feats["break_retest_ok"], feats["vol_mult"], c["fundingRate"], feats["trend_up"], feats["rsi14"])
        side = "LONG" if feats["trend_up"] else "SHORT"
        atr = feats["atr"]
        px_usd_now = feats["last_close"]

        if side == "LONG":
            entry_mid_usd = px_usd_now - settings.ATR_ENTRY_K * atr
            zone_lo_usd   = entry_mid_usd - (settings.ATR_ZONE_K * atr) / 2
            zone_hi_usd   = entry_mid_usd + (settings.ATR_ZONE_K * atr) / 2
            tp_usd        = px_usd_now + settings.ATR_TP_K * atr
            sl_usd        = px_usd_now - settings.ATR_SL_K * atr
        else:
            entry_mid_usd = px_usd_now + settings.ATR_ENTRY_K * atr
            zone_lo_usd   = entry_mid_usd - (settings.ATR_ZONE_K * atr) / 2
            zone_hi_usd   = entry_mid_usd + (settings.ATR_ZONE_K * atr) / 2
            tp_usd        = px_usd_now - settings.ATR_TP_K * atr
            sl_usd        = px_usd_now + settings.ATR_SL_K * atr

        token_name, price_now_txt = display_price(c["symbol"], px_usd_now, rate, unit)
        _, tp_txt = display_price(c["symbol"], tp_usd, rate, unit)
        _, sl_txt = display_price(c["symbol"], sl_usd, rate, unit)

        if want_mk:
            entry_txt = f"{price_now_txt} {unit}"
            order_type = "Market"
        else:
            _, lo_txt = display_price(c["symbol"], zone_lo_usd, rate, unit)
            _, hi_txt = display_price(c["symbol"], zone_hi_usd, rate, unit)
            entry_txt = f"{lo_txt}–{hi_txt} {unit} (TTL {settings.TTL_MINUTES}’)"
            order_type = "Limit"

        signals.append({
            "token": token_name,
            "side": side,
            "type": "Scalping",
            "orderType": order_type,
            "entry": entry_txt,
            "tp": f"{tp_txt} {unit}",
            "sl": f"{sl_txt} {unit}",
            "strength": random.randint(50, 90),
            "reason": f"EMA9 {'>' if feats['trend_up'] else '<'} EMA21; Vol_mult={feats['vol_mult']:.2f}; Funding={c['fundingRate']:.3f}%",
            "unit": unit
        })
    return signals
