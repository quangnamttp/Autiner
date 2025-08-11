# -*- coding: utf-8 -*-
"""
MEXC Futures — máy phát tín hiệu 'pro' cho autiner.

Điểm chính:
- Dữ liệu: MEXC futures (ticker, funding, kline 1m).
- Quyết định lệnh:
  • MARKET chỉ khi Break + Retest (≥2 nến) + EMA9>EMA21 (long) hoặc EMA9<EMA21 (short)
    + Volume_now ≥ MA20Vol × BREAK_VOL_MULT + |funding| < FUNDING_ABS_LIM
    + RSI(14) xác nhận hướng (long: > 52; short: < 48).
  • Ngược lại → LIMIT theo ATR(5m): Entry zone đón hồi, TTL, TP/SL theo ATR.
- Tránh đu đỉnh/đáy: dùng sigma biến động ngắn (5m) & dài (30m) để bỏ trường hợp quá nóng.
- Đa dạng: softmax theo điểm; coin lặp lại phải vượt median + REPEAT_BONUS_DELTA.
- Hiển thị VND giống ONUS (ROUND_DOWN):
  ≥100k: 0 lẻ; ≥1k: 2 lẻ; <1k: 4 lẻ (phù hợp coin siêu nhỏ như PEPE/SHIB…).
"""

from __future__ import annotations
import math
import time
import random
from decimal import Decimal, ROUND_DOWN
from typing import List, Dict, Tuple
from collections import deque

import requests

# ===== Settings (có mặc định để chạy ngay nếu thiếu trong settings.py) =====
try:
    from settings import (
        # API endpoints
        MEXC_TICKER_URL,          # ví dụ: https://contract.mexc.com/api/v1/contract/ticker
        MEXC_FUNDING_URL,         # ví dụ: https://contract.mexc.com/api/v1/contract/fundingRate
        MEXC_KLINES_URL,          # ví dụ: https://contract.mexc.com/api/v1/contract/kline?symbol={sym}&interval=Min1&limit=120
        USDVND_URL,               # ví dụ: https://api.exchangerate.host/latest?base=USD&symbols=VND

        # HTTP config
        HTTP_TIMEOUT, HTTP_RETRY,

        # FX cache TTL
        FX_CACHE_TTL,

        # Lọc & logic
        VOL24H_FLOOR,
        BREAK_VOL_MULT, FUNDING_ABS_LIM,
        ATR_ENTRY_K, ATR_ZONE_K, ATR_TP_K, ATR_SL_K,
        TTL_MINUTES,                   # TTL cho lệnh LIMIT (phút)
        TRAIL_START_K, TRAIL_STEP_K,   # (để dành)
        DIVERSITY_POOL_TOPN, SAME_PRICE_EPS, REPEAT_BONUS_DELTA,
    )
except Exception:
    # Endpoints mặc định
    MEXC_TICKER_URL  = "https://contract.mexc.com/api/v1/contract/ticker"
    MEXC_FUNDING_URL = "https://contract.mexc.com/api/v1/contract/fundingRate"
    MEXC_KLINES_URL  = "https://contract.mexc.com/api/v1/contract/kline?symbol={sym}&interval=Min1&limit=120"
    USDVND_URL       = "https://api.exchangerate.host/latest?base=USD&symbols=VND"

    # HTTP & cache
    HTTP_TIMEOUT = 10
    HTTP_RETRY   = 2
    FX_CACHE_TTL = 1800  # 30 phút

    # Lọc & logic
    VOL24H_FLOOR   = 200_000   # USDT: bỏ coin quá kém thanh khoản
    BREAK_VOL_MULT = 1.30
    FUNDING_ABS_LIM = 0.05     # 5%

    ATR_ENTRY_K = 0.30
    ATR_ZONE_K  = 0.20
    ATR_TP_K    = 1.00
    ATR_SL_K    = 0.80

    TTL_MINUTES   = 15
    TRAIL_START_K = 0.60
    TRAIL_STEP_K  = 0.50

    DIVERSITY_POOL_TOPN = 40
    SAME_PRICE_EPS      = 0.0005  # 0.05%
    REPEAT_BONUS_DELTA  = 0.40

# ===== Session & cache =====
_session = requests.Session()
_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124 Safari/537.36"}

_last_fx = {"ts": 0.0, "rate": 24500.0}     # tỷ giá fallback
_prev_volume: Dict[str, float] = {}          # quote vol 24h lần trước (USDT)
_hist_px: Dict[str, deque] = {}              # giá USD (đã auto-denom), lưu 3 mốc để ước r30/r60
_last_batch: set[str] = set()                # symbol batch trước (để hạn chế lặp)

# ===== Auto denom (tên hiển thị & nhân hệ số giống ONUS) =====
def auto_denom(symbol: str, last_usd: float, vnd_rate: float) -> Tuple[str, float, float]:
    """
    base_vnd = last_usd * vnd_rate
    - Nếu base_vnd < 0.001 -> nhân 1_000_000  (hậu tố '1M')
    - elif base_vnd < 1    -> nhân 1_000      (hậu tố '1000')
    - else                 -> giữ nguyên
    Trả: (display_symbol, adjusted_usd, multiplier)
    """
    base_vnd = (last_usd or 0.0) * (vnd_rate or 0.0)
    root = symbol.replace("_USDT", "")
    if base_vnd < 0.001:
        mul = 1_000_000.0
        disp = f"{root}1M"
    elif base_vnd < 1.0:
        mul = 1_000.0
        disp = f"{root}1000"
    else:
        mul = 1.0
        disp = root
    return disp, (last_usd or 0.0) * mul, mul

# ===== Format =====
def fmt_price_vnd(p: float) -> str:
    """VND giống ONUS (cắt bớt số lẻ — ROUND_DOWN), dùng dấu . ngăn nghìn."""
    p = float(p or 0.0)
    if p >= 100_000:
        s = f"{int(p):,}"
    elif p >= 1_000:
        q = Decimal(p).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
        s = f"{q:,.2f}"
    else:
        q = Decimal(p).quantize(Decimal("0.0001"), rounding=ROUND_DOWN)
        s = f"{q:,.4f}"
    return s.replace(",", ".")

def fmt_price_usd(p: float) -> str:
    s = f"{float(p or 0.0):.4f}".rstrip("0").rstrip(".")
    return s if s else "0"

def fmt_amount_int(x: float, unit: str) -> str:
    return f"{float(x or 0.0):,.0f} {unit}"

# ===== HTTP =====
def _get_json(url: str):
    for _ in range(max(1, HTTP_RETRY)):
        try:
            r = _session.get(url, headers=_HEADERS, timeout=HTTP_TIMEOUT)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
    return None

def usd_vnd_rate() -> float:
    now = time.time()
    if now - _last_fx["ts"] < FX_CACHE_TTL and _last_fx["rate"] > 0:
        return _last_fx["rate"]
    js = _get_json(USDVND_URL)
    if isinstance(js, dict):
        try:
            # exchangerate.host: {"rates":{"VND": <rate>}, ...}
            rate = float(js.get("rates", {}).get("VND"))
            if rate > 0:
                _last_fx.update(ts=now, rate=rate)
                return rate
        except Exception:
            pass
    return _last_fx["rate"]

# ===== Fetch live =====
def _fetch_tickers_live() -> List[dict]:
    """Chuẩn hoá:
    {
      symbol: "BTC_USDT",
      lastPrice: <USD>,
      volumeQuote: <USDT 24h>,
      change24h_pct: <percent>
    }
    """
    tick = _get_json(MEXC_TICKER_URL)
    items = []
    if isinstance(tick, dict) and (tick.get("success") or "data" in tick):
        arr = tick.get("data") or []
    elif isinstance(tick, list):
        arr = tick
    else:
        arr = []

    for it in arr:
        sym = it.get("symbol") or it.get("instrument_id")
        if not sym or not str(sym).endswith("_USDT"):
            continue
        try: last = float(it.get("lastPrice") or it.get("last") or it.get("price") or 0.0)
        except: last = 0.0
        try: qvol = float(it.get("quoteVol") or it.get("amount24") or it.get("turnover") or 0.0)
        except: qvol = 0.0
        try:
            raw = it.get("riseFallRate") or it.get("changeRate") or it.get("percent") or 0
            chg = float(raw)
            if abs(chg) < 1.0: chg *= 100.0
        except:
            chg = 0.0

        items.append({
            "symbol": sym,
            "lastPrice": last,
            "volumeQuote": qvol,
            "change24h_pct": chg,
        })
    return items

def _fetch_funding_live() -> Dict[str, float]:
    fjson = _get_json(MEXC_FUNDING_URL)
    fmap: Dict[str, float] = {}
    if isinstance(fjson, dict) and (fjson.get("success") or "data" in fjson):
        data = fjson.get("data") or fjson
        lst = data if isinstance(data, list) else data.get("list") or []
        for it in lst:
            s = it.get("symbol") or it.get("currency")
            if s and str(s).endswith("_USDT"):
                try: fr = float(it.get("fundingRate") or it.get("rate") or it.get("value") or 0.0)
                except: fr = 0.0
                fmap[s] = fr * 100.0
    return fmap

def _fetch_klines_1m(sym: str) -> List[dict]:
    url = MEXC_KLINES_URL.format(sym=sym)
    js = _get_json(url)
    out = []
    if isinstance(js, dict) and "data" in js:
        rows = js.get("data") or []
    elif isinstance(js, list):
        rows = js
    else:
        rows = []
    for r in rows:
        try:
            # MEXC kline thường: [time_ms, open, high, low, close, vol, ...]
            t = int(r[0]) // 1000
            o = float(r[1]); h = float(r[2]); l = float(r[3]); c = float(r[4]); v = float(r[5])
            out.append({"t": t, "o": o, "h": h, "l": l, "c": c, "v": v})
        except Exception:
            # Thử dạng dict
            try:
                t = int(r.get("time", 0)) // 1000
                o = float(r.get("open")); h = float(r.get("high")); l = float(r.get("low")); c = float(r.get("close")); v = float(r.get("vol"))
                out.append({"t": t, "o": o, "h": h, "l": l, "c": c, "v": v})
            except Exception:
                pass
    out.sort(key=lambda x: x["t"])
    return out[-120:]  # ~ 2h

# ===== Indicators =====
def ema(vals: List[float], period: int) -> List[float]:
    if not vals or period <= 1:
        return vals or []
    k = 2.0 / (period + 1.0)
    out = []
    ema_prev = vals[0]
    for i, x in enumerate(vals):
        if i == 0: ema_prev = x
        else:      ema_prev = x * k + ema_prev * (1 - k)
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

def sigma_change(kl: List[dict], n: int) -> float:
    if len(kl) < n + 1:
        return 0.0
    rets = []
    for i in range(-n, 0):
        p0 = kl[i-1]["c"]; p1 = kl[i]["c"]
        if p0 > 0:
            rets.append((p1 - p0) / p0 * 100.0)
    if not rets:
        return 0.0
    m = sum(rets)/len(rets)
    var = sum((x-m)**2 for x in rets)/len(rets)
    return math.sqrt(var)

def ma(vals: List[float], n: int) -> float:
    if not vals or len(vals) < n:
        return 0.0
    return sum(vals[-n:]) / n

# ===== Snapshot (USD nền; VND khi cần) =====
def market_snapshot(unit: str = "VND", topn: int = None) -> Tuple[List[dict], bool, float]:
    if topn is None:
        topn = DIVERSITY_POOL_TOPN
    items = _fetch_tickers_live()
    if not items:
        return [], False, usd_vnd_rate()
    fmap = _fetch_funding_live()
    rate = usd_vnd_rate()

    # lọc thanh khoản
    items = [d for d in items if d.get("volumeQuote", 0.0) >= VOL24H_FLOOR]
    if not items:
        return [], False, rate

    items.sort(key=lambda d: d.get("volumeQuote", 0.0), reverse=True)
    items = items[:max(5, topn)]

    out = []
    for it in items:
        sym = it["symbol"]
        disp, adj_usd, mul = auto_denom(sym, it["lastPrice"], rate)
        d = {
            "symbol": sym,
            "displaySymbol": disp,
            "lastPrice": adj_usd,                 # USD sau denom (để tính động lượng nhất quán)
            "volumeQuote": it["volumeQuote"],     # USDT
            "change24h_pct": it["change24h_pct"],
            "fundingRate": float(fmap.get(sym, 0.0)),
        }
        if unit == "VND":
            d["lastPriceVND"]   = float(adj_usd * rate)
            d["volumeValueVND"] = float(it["volumeQuote"] * rate)
        else:
            d["lastPriceVND"]   = None
            d["volumeValueVND"] = None
        out.append(d)
    return out, True, rate

# ===== Scoring & chọn tín hiệu =====
def _softmax(xs: List[float]) -> List[float]:
    if not xs: return []
    m = max(xs)
    exps = [math.exp(x - m) for x in xs]
    s = sum(exps) or 1.0
    return [e/s for e in exps]

def _momentum_features(sym: str, px_now_usd: float) -> Tuple[float, float]:
    dq = _hist_px.get(sym)
    if not dq or len(dq) < 2 or dq[-2] <= 0 or px_now_usd <= 0:
        return 0.0, 0.0
    r30 = (px_now_usd - dq[-2]) / dq[-2] * 100.0
    base = dq[-3] if len(dq) >= 3 and dq[-3] > 0 else dq[-2]
    r60 = (px_now_usd - base) / base * 100.0
    return r30, r60

def _score_coin(idx_rank: int, c: dict, prev_vol: float) -> Tuple[float, float, float]:
    px_usd  = float(c.get("lastPrice", 0.0))
    chg24   = float(c.get("change24h_pct", 0.0))
    fr      = float(c.get("fundingRate", 0.0))
    volq    = float(c.get("volumeQuote", 0.0))

    r30, r60 = _momentum_features(c["symbol"], px_usd)
    accel = max(0.0, r30 - 0.5 * r60)
    vol_spike = (volq / prev_vol) if prev_vol > 0 else 1.0
    vol_spike = min(vol_spike, 5.0)

    still_pen = 0.0
    dq = _hist_px.get(c["symbol"])
    if dq and len(dq) >= 2:
        px_prev = dq[-2]
        if px_prev > 0 and abs(px_usd - px_prev) / px_prev < SAME_PRICE_EPS:
            still_pen = 0.7

    base = 1.0 / (idx_rank + 1.0)
    dyn  = max(0.0, abs(r30)) / 2.0
    acc  = accel / 2.0
    fnd  = min(abs(fr) / 0.05, 2.0) * 0.3
    vsp  = (vol_spike - 1.0) * 0.4

    score = base + dyn + acc + fnd + vsp - still_pen
    return score, r30, r60

def _build_reason(strategy: str, ctx: dict) -> str:
    trend_txt = "EMA9 > EMA21 (xu hướng tăng)" if ctx["ema9"] > ctx["ema21"] else "EMA9 < EMA21 (xu hướng giảm)"
    rsi_zone = "trên 50 (ủng hộ Long)" if ctx["rsi14"] >= 52 else ("dưới 50 (ủng hộ Short)" if ctx["rsi14"] <= 48 else "vùng trung tính")

    if strategy == "MARKET":
        return (
            "• Break + Retest giữ 2 nến, " + trend_txt + "\n"
            f"• Volume = {ctx['vol_mult']:.2f}× MA20Vol (xác nhận), Funding {ctx['funding']:+.3f}%\n"
            f"• RSI(14) = {ctx['rsi14']:.1f} ({rsi_zone}); r30={ctx['r30']:+.2f}%, r60={ctx['r60']:+.2f}% ⇒ accel={ctx['accel']:+.2f}%\n"
            "• TP/SL dựa ATR(5m); trailing nếu đi đúng ≥ 0.6×ATR"
        )
    else:
        return (
            "• Ưu tiên LIMIT đón hồi về vùng EMA (9/21) cùng xu hướng, " + trend_txt + "\n"
            f"• RSI(14) = {ctx['rsi14']:.1f} ({rsi_zone}); Volume = {ctx['vol_mult']:.2f}× MA20Vol; Funding {ctx['funding']:+.3f}%\n"
            f"• Dựng Entry zone/TP/SL bằng ATR(5m); TTL {TTL_MINUTES}’ (không khớp sẽ huỷ)"
        )

def _need_market(break_retest_ok: bool, vol_mult: float, funding: float, r30: float, r60: float, ema_up: bool, rsi14: float) -> bool:
    if not break_retest_ok:
        return False
    if vol_mult < BREAK_VOL_MULT:
        return False
    if abs(funding) >= FUNDING_ABS_LIM:
        return False
    # RSI xác nhận hướng
    if ema_up and rsi14 < 52:
        return False
    if (not ema_up) and rsi14 > 48:
        return False
    accel = r30 - 0.5 * r60
    if r30 > 0 and accel > 0 and ema_up:
        return True
    if r30 < 0 and accel < 0 and (not ema_up):
        return True
    return False

def _analyze_klines_for(sym: str) -> dict:
    """Tính EMA9/EMA21 (từ 1m), ATR(5m), MA20Vol, sigma, RSI(14), break+retest."""
    kl = _fetch_klines_1m(sym)
    if len(kl) < 30:
        return {"ok": False}

    closes = [k["c"] for k in kl]
    vols   = [k["v"] for k in kl]
    ema9   = ema(closes, 9)
    ema21  = ema(closes, 21)
    atr    = atr_5m(kl)
    ma20v  = ma(vols, 20)
    sig5   = sigma_change(kl, 5)
    sig30  = sigma_change(kl, 30)
    rsi14  = rsi(closes, 14)

    last  = closes[-1]
    prev20_max = max(closes[-21:-1]) if len(closes) >= 21 else max(closes[:-1])
    prev20_min = min(closes[-21:-1]) if len(closes) >= 21 else min(closes[:-1])
    up   = last > prev20_max and (ema9[-1] > ema21[-1]) and (closes[-1] > ema21[-1] and closes[-2] > ema21[-2])
    down = last < prev20_min and (ema9[-1] < ema21[-1]) and (closes[-1] < ema21[-1] and closes[-2] < ema21[-2])
    br_ok = up or down

    vol_now = vols[-1]
    vol_mult = (vol_now / ma20v) if ma20v > 0 else 1.0

    return {
        "ok": True,
        "atr": atr,
        "ema9": ema9[-1],
        "ema21": ema21[-1],
        "rsi14": rsi14,
        "vol_ma20": ma20v,
        "vol_now": vol_now,
        "vol_mult": vol_mult,
        "sigma5": sig5,
        "sigma30": sig30,
        "break_retest_ok": br_ok,
        "trend_up": ema9[-1] > ema21[-1],
        "last_close": last,
    }

def smart_pick_signals(unit: str, n_scalp: int = 5):
    """
    Trả: (signals, highlights, live, rate)
    signal: dict {token, side, type, orderType, entry/zone, tp, sl, strength, reason, unit}
    """
    coins, live, rate = market_snapshot(unit="USD", topn=DIVERSITY_POOL_TOPN)
    if not live or not coins:
        return [], [], live, rate

    # Cập nhật lịch sử giá để tính r30/r60 (dựa USD đã auto-denom)
    now_rate = usd_vnd_rate()
    for c in coins:
        disp, adj_usd, _ = auto_denom(c["symbol"], c["lastPrice"], now_rate)
        dq = _hist_px.setdefault(c["symbol"], deque(maxlen=3))
        dq.append(float(adj_usd))

    # Scoring + đặc trưng nến
    pool = []
    prev_vol_map = {c["symbol"]: _prev_volume.get(c["symbol"], 0.0) for c in coins}
    for idx, c in enumerate(coins):
        score, r30, r60 = _score_coin(idx, c, prev_vol_map.get(c["symbol"], 0.0))
        feats = _analyze_klines_for(c["symbol"])
        if not feats.get("ok"):
            continue
        pool.append((score, r30, r60, idx, c, feats))

    if not pool:
        return [], [], live, rate

    # Hạn chế lặp: coin trùng batch trước phải có score vượt median + REPEAT_BONUS_DELTA
    scores_only = [p[0] for p in pool]
    median = sorted(scores_only)[len(scores_only)//2]
    keep = []
    for score, r30, r60, idx, c, feats in pool:
        if c["symbol"] in _last_batch:
            if score >= median + REPEAT_BONUS_DELTA:
                keep.append((score, r30, r60, idx, c, feats))
        else:
            keep.append((score, r30, r60, idx, c, feats))
    if not keep:
        keep = pool

    # Ưu tiên điểm cao nhưng vẫn đa dạng
    keep.sort(key=lambda x: x[0], reverse=True)
    probs = _softmax([k[0] for k in keep])
    bag, p = keep[:], probs[:]
    picked = []
    for _ in range(min(n_scalp, len(bag))):
        r = random.random()
        acc = 0.0
        chosen_idx = 0
        for i, w in enumerate(p):
            acc += w
            if r <= acc:
                chosen_idx = i
                break
        picked.append(bag.pop(chosen_idx))
        p.pop(chosen_idx)
        if p:
            s = sum(p)
            p = [x/s for x in p]

    # Dựng tín hiệu
    signals = []
    highlights = []

    for rank, (score, r30, r60, idx, c, feats) in enumerate(picked):
        change  = c.get("change24h_pct", 0.0)
        funding = c.get("fundingRate", 0.0)

        ema_up  = feats["trend_up"]
        rsi14   = feats["rsi14"]
        want_mk = _need_market(
            feats["break_retest_ok"], feats["vol_mult"], funding, r30, r60, ema_up, rsi14
        )

        accel = r30 - 0.5*r60
        side = "LONG" if (r30 > 0 and accel >= 0) else "SHORT"

        atr  = max(0.0, feats["atr"])
        px_u = float(_hist_px[c["symbol"]][-1])  # USD (đã denom)
        if unit == "VND":
            px = px_u * now_rate
            one_atr = atr * now_rate
            fmtp = fmt_price_vnd
            volq_disp = fmt_amount_int(c.get("volumeQuote", 0.0) * now_rate, "VND")
            unit_tag = "VND"
        else:
            px = px_u
            one_atr = atr
            fmtp = fmt_price_usd
            volq_disp = fmt_amount_int(c.get("volumeQuote", 0.0), "USDT")
            unit_tag = "USD"

        if side == "LONG":
            entry_mid = px - ATR_ENTRY_K * one_atr
            zone_lo   = entry_mid - (ATR_ZONE_K * one_atr) / 2
            zone_hi   = entry_mid + (ATR_ZONE_K * one_atr) / 2
            tp_val    = px + ATR_TP_K * one_atr
            sl_val    = px - ATR_SL_K * one_atr
        else:
            entry_mid = px + ATR_ENTRY_K * one_atr
            zone_lo   = entry_mid - (ATR_ZONE_K * one_atr) / 2
            zone_hi   = entry_mid + (ATR_ZONE_K * one_atr) / 2
            tp_val    = px - ATR_TP_K * one_atr
            sl_val    = px + ATR_SL_K * one_atr

        order_type = "Market" if want_mk else "Limit"
        token_disp, _, _ = auto_denom(c["symbol"], c["lastPrice"], now_rate)
        strength = int(max(35, min(95, 65 + score*8 - rank*3)))

        ctx = {
            "r30": r30, "r60": r60, "accel": accel,
            "vol_mult": feats["vol_mult"],
            "funding": funding,
            "ema9": feats["ema9"], "ema21": feats["ema21"],
            "rsi14": rsi14
        }
        reason = _build_reason(order_type.upper(), ctx)

        entry_text = f"{fmtp(px)} {unit_tag}" if order_type == "Market" \
                     else f"{fmtp(zone_lo)}–{fmtp(zone_hi)} {unit_tag}  (TTL {TTL_MINUTES}’)"

        signals.append({
            "token": token_disp,
            "side": side,
            "type": "Scalping",
            "orderType": order_type,
            "entry": entry_text,
            "tp": f"{fmtp(tp_val)} {unit_tag}",
            "sl": f"{fmtp(sl_val)} {unit_tag}",
            "strength": strength,
            "reason": f"{reason}\n• VolQ≈{volq_disp}",
            "unit": unit_tag
        })

    # cập nhật batch & prev volume (NHỚ đặt global trước khi gán!)
    global _last_batch, _prev_volume
    _last_batch = {c["symbol"] for (_,_,_,_,c,_) in picked}
    _prev_volume = {c["symbol"]: c.get("volumeQuote", 0.0) for c in coins}

    return signals, highlights, live, now_rate
