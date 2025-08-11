# -*- coding: utf-8 -*-
"""
MEXC futures helper: lấy ticker/funding, auto-denom giống ONUS,
chọn tín hiệu thông minh + fallback để không rơi batch.
"""

import time, math, random, requests
from collections import deque
from typing import List, Dict, Tuple

# --- settings (bắt buộc) ---
from settings import (
    MEXC_TICKER_URL,     # ví dụ: https://contract.mexc.com/api/v1/contract/ticker
    MEXC_FUNDING_URL,    # ví dụ: https://contract.mexc.com/api/v1/contract/fundingRate
    USDVND_URL,          # ví dụ: https://open.er-api.com/v6/latest/USD
    HTTP_TIMEOUT, HTTP_RETRY,
    FX_CACHE_TTL,
)

# --- núm chỉnh (có default nếu settings không khai báo) ---
try:
    from settings import (
        DIVERSITY_POOL_TOPN,     # lấy bao nhiêu mã làm pool (volume-top) để chấm
        VOL_FLOOR_USDT_SMART,    # lọc volume tối thiểu
        MIN_ABS_R30_PCT,         # |r30| nhỏ nhất để coi là có động lượng
        SAME_PRICE_EPS,          # coi như đứng im nếu |Δ|/price < eps
        REPEAT_BONUS_DELTA,      # yêu cầu vượt median để được lặp batch
    )
except Exception:
    DIVERSITY_POOL_TOPN = 40
    VOL_FLOOR_USDT_SMART = 150_000
    MIN_ABS_R30_PCT = 0.25
    SAME_PRICE_EPS = 0.0015
    REPEAT_BONUS_DELTA = 0.40

# ===== Session & cache =====
_session = requests.Session()
_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124 Safari/537.36"}

_last_fx = {"ts": 0.0, "rate": 24500.0}
_prev_volume: Dict[str, float] = {}     # symbol -> quote volume (USDT) slot trước
_hist_px: Dict[str, deque]  = {}        # symbol -> deque 3 giá USD gần nhất (≈ 90’)
_last_batch: set[str] = set()           # các symbol đã gửi ở slot trước

# ====== Formatter ======
def _with_dot_grouping(n: float, digits: int) -> str:
    s = f"{n:,.{digits}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")

def fmt_price_vnd(p: float) -> str:
    """
    ONUS style:
      - >= 100_000   : 0 chữ số thập phân
      - >= 1_000     : 2 chữ số thập phân
      - else (<1_000): 4 chữ số thập phân
    """
    p = float(p or 0.0)
    if p >= 100_000: return _with_dot_grouping(p, 0)
    if p >= 1_000:   return _with_dot_grouping(p, 2)
    return _with_dot_grouping(p, 4)

def fmt_price_usd(p: float) -> str:
    s = f"{float(p or 0.0):.4f}".rstrip("0").rstrip(".")
    return s if s else "0"

def fmt_amount_int(x: float, unit: str) -> str:
    return _with_dot_grouping(float(x or 0.0), 0) + f" {unit}"

# ====== HTTP helper ======
def _get_json(url: str):
    for _ in range(max(1, HTTP_RETRY)):
        try:
            r = _session.get(url, headers=_UA, timeout=HTTP_TIMEOUT)
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
        v = js.get("rates", {}).get("VND")
        try:
            rate = float(v)
            if rate > 0:
                _last_fx.update(ts=now, rate=rate)
                return rate
        except Exception:
            pass
    return _last_fx["rate"]

# ====== Auto denomination (giống cách ONUS nhân 1k / 1M cho mệnh giá nhỏ) ======
def auto_denom(symbol: str, last_usd: float, vnd_rate: float) -> Tuple[str, float, float]:
    """
    Trả (display_symbol, last_usd_adjusted, multiplier)
    """
    base_vnd = (last_usd or 0.0) * (vnd_rate or 0.0)
    root = symbol.replace("_USDT", "")
    if base_vnd < 0.001:     # quá nhỏ -> 1M
        return f"{root}1M", last_usd * 1_000_000.0, 1_000_000.0
    if base_vnd < 1.0:       # nhỏ -> 1000
        return f"{root}1000", last_usd * 1_000.0, 1_000.0
    return root, last_usd, 1.0

# ====== Fetch live ======
def _fetch_tickers_live() -> List[dict]:
    """
    Chuẩn hoá:
      symbol: "BTC_USDT"
      lastPrice: <USD>
      volumeQuote: <USDT 24h>
      change24h_pct: <percent>
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
                fmap[s] = fr * 100.0  # %
    return fmap

# ====== Snapshot sau auto-denom ======
def market_snapshot(unit: str = "VND", topn: int = 40) -> Tuple[List[dict], bool, float]:
    items = _fetch_tickers_live()
    if not items:
        return [], False, usd_vnd_rate()
    fmap = _fetch_funding_live()
    rate = usd_vnd_rate()

    items.sort(key=lambda d: d.get("volumeQuote", 0.0), reverse=True)
    items = items[:max(5, topn)]

    out = []
    for it in items:
        sym = it["symbol"]
        disp, adj_usd, mul = auto_denom(sym, it["lastPrice"], rate)
        d = {
            "symbol": sym,
            "displaySymbol": disp,
            "lastPrice": adj_usd,
            "volumeQuote": it["volumeQuote"],
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

# ====== Chấm điểm & chọn tín hiệu ======
def _softmax(xs):
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
    r60 = (px_now_usd - dq[-3]) / dq[-3] * 100.0 if len(dq) >= 3 and dq[-3] > 0 else 0.0
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

def _side_from_momo_funding(r30: float, change24h: float, funding: float) -> str:
    if r30 > 0.0 and (funding >= -0.02 or change24h >= 0): return "LONG"
    if r30 < 0.0 and (funding <= 0.02 or change24h <= 0):  return "SHORT"
    return "LONG" if change24h >= 0 else "SHORT"

def _fallback_make_signals(unit: str, coins: List[dict], n: int, rate: float):
    """Khi pool rỗng: lấy top theo volume và tạo lệnh an toàn để không trượt batch."""
    out = []
    now_rate = rate or usd_vnd_rate()
    for c in coins[:n]:
        change  = c.get("change24h_pct", 0.0)
        funding = c.get("fundingRate", 0.0)
        side = "LONG" if change >= 0 else "SHORT"

        disp, adj_usd, _ = auto_denom(c["symbol"], c["lastPrice"], now_rate)
        if unit == "VND":
            px = adj_usd * now_rate
            tp = px * (1.004 if side=="LONG" else 0.996)
            sl = px * (0.996 if side=="LONG" else 1.004)
            entry = fmt_price_vnd(px) + " VND"
            tp_s  = fmt_price_vnd(tp) + " VND"
            sl_s  = fmt_price_vnd(sl) + " VND"
            unit_tag = "VND"
            volq = fmt_amount_int(c.get("volumeQuote", 0.0)*now_rate, "VND")
        else:
            px = adj_usd
            tp = px * (1.004 if side=="LONG" else 0.996)
            sl = px * (0.996 if side=="LONG" else 1.004)
            entry = fmt_price_usd(px) + " USDT"
            tp_s  = fmt_price_usd(tp) + " USDT"
            sl_s  = fmt_price_usd(sl) + " USDT"
            unit_tag = "USD"
            volq = fmt_amount_int(c.get("volumeQuote", 0.0), "USDT")

        out.append({
            "token": disp, "side": side, "type": "Scalping", "orderType": "Market",
            "entry": entry, "tp": tp_s, "sl": sl_s, "strength": 45,
            "reason": f"fallback • funding={funding:+.3f}%, Δ24h={change:+.2f}%, VolQ≈{volq}",
            "unit": unit_tag
        })
    return out

# ... (nguyên phần đầu file y như bản bạn đang có)

def smart_pick_signals(unit: str, n_scalp=5):
    # >>> FIX: khai báo global trước khi đụng tới 2 biến này
    global _last_batch, _prev_volume

    coins, live, rate = market_snapshot(unit="USD", topn=DIVERSITY_POOL_TOPN)
    if not live or not coins:
        return [], [], live, rate

    # lọc sơ bộ
    pool = []
    prev_vol_map = {c["symbol"]: _prev_volume.get(c["symbol"], 0.0) for c in coins}
    for idx, c in enumerate(coins):
        if c.get("volumeQuote", 0.0) < VOL_FLOOR_USDT_SMART:
            continue
        score, r30, r60 = _score_coin(idx, c, prev_vol_map.get(c["symbol"], 0.0))
        if abs(r30) < MIN_ABS_R30_PCT:
            continue
        pool.append((score, r30, r60, idx, c))

    # nếu rỗng, fallback (không báo lỗi)
    if not pool:
        fallback = _fallback_make_signals(unit, coins, n_scalp, rate)
        return fallback, [], True, rate

    # hạn chế lặp
    scores_only = [p[0] for p in pool]
    median = sorted(scores_only)[len(scores_only)//2]
    keep = []
    for score, r30, r60, idx, c in pool:
        if c["symbol"] in _last_batch:
            if score >= median + REPEAT_BONUS_DELTA:
                keep.append((score, r30, r60, idx, c))
        else:
            keep.append((score, r30, r60, idx, c))
    if not keep:
        keep = pool

    # softmax sampling
    keep.sort(key=lambda x: x[0], reverse=True)
    probs = _softmax([k[0] for k in keep])
    bag, p = keep[:], probs[:]
    chosen = []
    for _ in range(min(n_scalp, len(bag))):
        r = random.random()
        acc = 0.0
        j = 0
        for i, w in enumerate(p):
            acc += w
            if r <= acc:
                j = i; break
        chosen.append(bag.pop(j))
        p.pop(j)
        if p:
            s = sum(p); p = [x/s for x in p]

    # dựng tín hiệu
    signals = []
    now_rate = usd_vnd_rate()
    for rank, (score, r30, r60, idx, c) in enumerate(chosen):
        change  = c.get("change24h_pct", 0.0)
        funding = c.get("fundingRate", 0.0)
        side = _side_from_momo_funding(r30, change, funding)

        strength = int(max(35, min(95, 65 + score*8 - rank*3)))

        disp, adj_usd, mul = auto_denom(c["symbol"], c["lastPrice"], now_rate)
        if unit == "VND":
            px = adj_usd * now_rate
            tp = px * (1.006 if side == "LONG" else 0.994)
            sl = px * (0.992 if side == "LONG" else 1.008)
            entry = fmt_price_vnd(px) + " VND"
            tp_s  = fmt_price_vnd(tp) + " VND"
            sl_s  = fmt_price_vnd(sl) + " VND"
            unit_tag = "VND"
            volq = fmt_amount_int(c.get("volumeQuote", 0.0) * now_rate, "VND")
        else:
            px = adj_usd
            tp = px * (1.006 if side == "LONG" else 0.994)
            sl = px * (0.992 if side == "LONG" else 1.008)
            entry = fmt_price_usd(px) + " USDT"
            tp_s  = fmt_price_usd(tp) + " USDT"
            sl_s  = fmt_price_usd(sl) + " USDT"
            unit_tag = "USD"
            volq = fmt_amount_int(c.get("volumeQuote", 0.0), "USDT")

        signals.append({
            "token": disp, "side": side, "type": "Scalping", "orderType": "Market",
            "entry": entry, "tp": tp_s, "sl": sl_s, "strength": strength,
            "reason": f"r30={r30:+.2f}%, accel={max(0.0, r30-0.5*r60):+.2f}%, funding={funding:+.3f}%, VolQ≈{volq}",
            "unit": unit_tag
        })

        dq = _hist_px.setdefault(c["symbol"], deque(maxlen=3))
        dq.append(float(adj_usd))

    # cập nhật batch & volume cho slot sau
    _last_batch = {c["symbol"] for (_,_,_,_,c) in chosen}
    _prev_volume = {c["symbol"]: c.get("volumeQuote", 0.0) for c in coins}

    return signals, [], True, now_rate
