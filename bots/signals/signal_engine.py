# bots/signals/signal_engine.py
# -*- coding: utf-8 -*-
"""
Autiner — Signal Engine (Scalping, pro)

- Lấy snapshot MEXC (tickers + funding) -> lọc thanh khoản theo VOL24H_FLOOR
- Phân tích 1m/5m (EMA9/21, ATR, RSI, sigma, break+retest)
- Chấm điểm + chọn ngẫu nhiên theo softmax để đa dạng
- Trả về danh sách tín hiệu cho Telegram bot

Lưu ý:
- Dùng đúng formatter đang có: bots/pricing/onus_format.py -> display_price()
"""

from __future__ import annotations
import math
import time
import random
from typing import List, Dict, Tuple
from collections import deque
import requests

from settings import (
    MEXC_TICKER_URL, MEXC_FUNDING_URL, MEXC_KLINES_URL, USDVND_URL,
    HTTP_TIMEOUT, HTTP_RETRY, FX_CACHE_TTL,
    VOL24H_FLOOR, BREAK_VOL_MULT, FUNDING_ABS_LIM,
    ATR_ENTRY_K, ATR_ZONE_K, ATR_TP_K, ATR_SL_K,
    TTL_MINUTES, TRAIL_START_K, TRAIL_STEP_K,
    DIVERSITY_POOL_TOPN, SAME_PRICE_EPS, REPEAT_BONUS_DELTA,
)

# Đúng đường dẫn theo repo hiện tại
from bots.pricing.onus_format import display_price

_session = requests.Session()
_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124 Safari/537.36"}

_last_fx = {"ts": 0.0, "rate": 24500.0}  # fallback an toàn
_prev_volume: Dict[str, float] = {}
_hist_px: Dict[str, deque] = {}
_last_batch: set[str] = set()

# ---------------- HTTP helpers ----------------
def _get_json(url: str):
    for _ in range(max(1, HTTP_RETRY)):
        try:
            r = _session.get(url, headers=_HEADERS, timeout=HTTP_TIMEOUT)
            if r.status_code == 200:
                return r.json()
            time.sleep(0.15)
        except Exception:
            time.sleep(0.15)
    return None

def usd_vnd_rate() -> float:
    now = time.time()
    if now - _last_fx["ts"] < FX_CACHE_TTL and _last_fx["rate"] > 0:
        return _last_fx["rate"]
    js = _get_json(USDVND_URL)
    if isinstance(js, dict):
        try:
            rate = float(js.get("rates", {}).get("VND"))
            if rate > 0:
                _last_fx["ts"] = now
                _last_fx["rate"] = rate
                return rate
        except Exception:
            pass
    # fallback
    return _last_fx["rate"]

# ---------------- Live data ----------------
def _fetch_tickers_live() -> List[dict]:
    tick = _get_json(MEXC_TICKER_URL)
    items: List[dict] = []
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

        # last
        try:
            last = float(it.get("lastPrice") or it.get("last") or it.get("price") or it.get("close") or 0.0)
        except Exception:
            last = 0.0

        # ---- robust quote volume (vá chính) ----
        qvol = 0.0
        for k in ("quoteVol", "amount24", "turnover", "turnover24", "turnover24h",
                  "quote_volume", "volValue", "volQuote", "volumeQuote"):
            if k in it and it[k] not in (None, "", "0"):
                try:
                    qvol = float(it[k])
                    break
                except Exception:
                    pass
        if qvol == 0.0:
            # tự suy ra từ base volume * last nếu có
            for k in ("volume24", "vol24", "baseVol", "volume"):
                if k in it and it[k] not in (None, "", "0"):
                    try:
                        base_vol = float(it[k])
                        if base_vol > 0 and last > 0:
                            qvol = base_vol * last
                            break
                    except Exception:
                        pass

        # % change 24h
        try:
            raw = it.get("riseFallRate") or it.get("changeRate") or it.get("percent") or 0
            chg = float(raw)
            if abs(chg) < 1.0:
                chg *= 100.0
        except Exception:
            chg = 0.0

        items.append({
            "symbol": str(sym),
            "lastPrice": last,
            "volumeQuote": qvol,
            "change24h_pct": chg,
        })
    return items

def _fetch_funding_live() -> Dict[str, float]:
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
                fr *= 100.0
            fmap[str(s)] = fr
        except Exception:
            continue
    return fmap

def _fetch_klines_1m(sym: str) -> List[dict]:
    url = MEXC_KLINES_URL.format(sym=sym)
    js = _get_json(url)
    out: List[dict] = []
    if isinstance(js, dict) and "data" in js:
        rows = js.get("data") or []
    elif isinstance(js, list):
        rows = js
    else:
        rows = []
    for r in rows:
        try:
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
    if not vals or len(vals) < n: return 0.0
    return sum(vals[-n:]) / n

# ---------------- Snapshot + scoring ----------------
def market_snapshot(unit: str = "VND", topn: int | None = None) -> Tuple[List[dict], bool, float]:
    if topn is None:
        topn = DIVERSITY_POOL_TOPN
    items = _fetch_tickers_live()
    if not items:
        return [], False, usd_vnd_rate()
    fmap = _fetch_funding_live()
    rate = usd_vnd_rate()

    # lọc thanh khoản
    items = [d for d in items if float(d.get("volumeQuote", 0.0)) >= float(VOL24H_FLOOR or 0)]
    if not items:
        return [], False, rate

    items.sort(key=lambda d: d.get("volumeQuote", 0.0), reverse=True)
    items = items[:max(5, topn)]
    out = []
    for it in items:
        sym = it["symbol"]
        out.append({
            "symbol": sym,
            "lastPrice": float(it["lastPrice"]),
            "volumeQuote": float(it["volumeQuote"]),
            "change24h_pct": float(it["change24h_pct"]),
            "fundingRate": float(fmap.get(sym, 0.0)),
        })
    return out, True, rate

def _softmax(xs: List[float]) -> List[float]:
    if not xs: return []
    m = max(xs)
    exps = [math.exp(x - m) for x in xs]
    s = sum(exps) or 1.0
    return [e/s for e in exps]

def _momentum_features(sym: str, px_now_usd_adj: float) -> Tuple[float, float]:
    dq = _hist_px.get(sym)
    if not dq or len(dq) < 2 or dq[-2] <= 0 or px_now_usd_adj <= 0:
        return 0.0, 0.0
    r30 = (px_now_usd_adj - dq[-2]) / dq[-2] * 100.0
    base = dq[-3] if len(dq) >= 3 and dq[-3] > 0 else dq[-2]
    r60 = (px_now_usd_adj - base) / base * 100.0
    return r30, r60

def _score_coin(idx_rank: int, c: dict, prev_vol: float) -> Tuple[float, float, float]:
    px_usd = float(c.get("lastPrice", 0.0))
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
    rsi_zone = "ủng hộ Long" if ctx["rsi14"] >= 52 else ("ủng hộ Short" if ctx["rsi14"] <= 48 else "trung tính")
    if strategy == "MARKET":
        return (
            "• Break + Retest ≥2 nến, " + trend_txt + "\n"
            f"• Vol_now = {ctx['vol_mult']:.2f}× MA20Vol; Funding {ctx['funding']:+.3f}%\n"
            f"• RSI(14) = {ctx['rsi14']:.1f} ({rsi_zone}); r30={ctx['r30']:+.2f}%, r60={ctx['r60']:+.2f}% (accel={ctx['accel']:+.2f}%)\n"
            "• TP/SL dựa ATR(5m); trailing nếu đi đúng ≥ 0.6×ATR"
        )
    else:
        return (
            "• LIMIT đón hồi về vùng EMA(9/21) cùng xu hướng, " + trend_txt + "\n"
            f"• RSI(14) = {ctx['rsi14']:.1f} ({rsi_zone}); Vol_now = {ctx['vol_mult']:.2f}× MA20Vol; Funding {ctx['funding']:+.3f}%\n"
            f"• Zone/TP/SL dựng bằng ATR(5m); TTL {TTL_MINUTES}’ (không khớp sẽ huỷ)"
        )

def _need_market(break_retest_ok: bool, vol_mult: float, funding: float, r30: float, r60: float, ema_up: bool, rsi14: float) -> bool:
    if not break_retest_ok: return False
    if vol_mult < BREAK_VOL_MULT: return False
    if abs(funding) >= FUNDING_ABS_LIM: return False
    if ema_up and rsi14 < 52: return False
    if (not ema_up) and rsi14 > 48: return False
    accel = r30 - 0.5 * r60
    if r30 > 0 and accel > 0 and ema_up: return True
    if r30 < 0 and accel < 0 and (not ema_up): return True
    return False

def _analyze_klines_for(sym: str) -> dict:
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

# ---------------- Public API ----------------
def generate_scalping_signals(unit: str = "VND", n_scalp: int = 5):
    global _last_batch, _prev_volume
    coins, live, rate = market_snapshot(unit="USD", topn=DIVERSITY_POOL_TOPN)
    if not live or not coins:
        return [], [], live, rate

    # lưu lịch sử giá để tính động lượng
    for c in coins:
        dq = _hist_px.setdefault(c["symbol"], deque(maxlen=3))
        dq.append(float(c["lastPrice"]))

    # tính điểm + lọc
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

    # đa dạng hoá
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

    # dựng tín hiệu
    signals = []
    highlights = []
    usd_vnd = usd_vnd_rate()
    for rank, (score, r30, r60, idx, c, feats) in enumerate(picked):
        funding = c.get("fundingRate", 0.0)
        ema_up  = feats["trend_up"]
        rsi14   = feats["rsi14"]
        want_mk = _need_market(
            feats["break_retest_ok"], feats["vol_mult"],
            funding, r30, r60, ema_up, rsi14
        )
        accel = r30 - 0.5*r60
        side = "LONG" if (r30 > 0 and accel >= 0) else "SHORT"
        atr = max(0.0, float(feats["atr"]))
        px_usd_now = float(feats["last_close"])

        if side == "LONG":
            entry_mid_usd = px_usd_now - ATR_ENTRY_K * atr
            zone_lo_usd   = entry_mid_usd - (ATR_ZONE_K * atr) / 2
            zone_hi_usd   = entry_mid_usd + (ATR_ZONE_K * atr) / 2
            tp_usd        = px_usd_now + ATR_TP_K * atr
            sl_usd        = px_usd_now - ATR_SL_K * atr
        else:
            entry_mid_usd = px_usd_now + ATR_ENTRY_K * atr
            zone_lo_usd   = entry_mid_usd - (ATR_ZONE_K * atr) / 2
            zone_hi_usd   = entry_mid_usd + (ATR_ZONE_K * atr) / 2
            tp_usd        = px_usd_now - ATR_TP_K * atr
            sl_usd        = px_usd_now + ATR_SL_K * atr

        unit_tag = unit.upper()
        token_name, price_now_txt = display_price(c["symbol"], px_usd_now, usd_vnd, unit_tag)
        _, tp_txt  = display_price(c["symbol"], tp_usd,      usd_vnd, unit_tag)
        _, sl_txt  = display_price(c["symbol"], sl_usd,      usd_vnd, unit_tag)

        if want_mk:
            entry_txt = f"{price_now_txt} {unit_tag}"
            order_type = "Market"
        else:
            _, lo_txt = display_price(c["symbol"], zone_lo_usd, usd_vnd, unit_tag)
            _, hi_txt = display_price(c["symbol"], zone_hi_usd, usd_vnd, unit_tag)
            order_type = "Limit"
            entry_txt = f"{lo_txt}–{hi_txt} {unit_tag}  (TTL {TTL_MINUTES}’)"

        strength = int(max(35, min(95, 65 + score*8 - rank*3)))
        ctx = {
            "r30": r30, "r60": r60, "accel": accel,
            "vol_mult": feats["vol_mult"],
            "funding": funding,
            "ema9": feats["ema9"], "ema21": feats["ema21"],
            "rsi14": rsi14
        }
        reason = _build_reason("MARKET" if want_mk else "LIMIT", ctx)

        signals.append({
            "token": token_name,
            "side": side,
            "type": "Scalping",
            "orderType": order_type,
            "entry": entry_txt,
            "tp": f"{tp_txt} {unit_tag}",
            "sl": f"{sl_txt} {unit_tag}",
            "strength": strength,
            "reason": reason,
            "unit": unit_tag
        })

    _last_batch = {c["symbol"] for (_,_,_,_,c,_) in picked}
    _prev_volume = {c["symbol"]: c.get("volumeQuote", 0.0) for c in coins}

    return signals, highlights, live, usd_vnd

# Wrapper tương thích Telegram bot (trả list)
def generate_signals(unit: str = "VND", n: int = 5):
    sigs, _, _, _ = generate_scalping_signals(unit=unit, n_scalp=n)
    return sigs
