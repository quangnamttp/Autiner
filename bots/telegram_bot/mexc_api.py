import time
import requests
from typing import List, Dict
from settings import (
    MEXC_TICKER_URL, MEXC_FUNDING_URL,
    USDVND_URL, HTTP_TIMEOUT, HTTP_RETRY,
    FX_CACHE_TTL, ALERT_FUNDING_ABS, ALERT_VOLUME_SPIKE
)

_session = requests.Session()
_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124 Safari/537.36"}

_last_fx = {"ts": 0.0, "rate": 24500.0}  # fallback khi chưa lấy được tỷ giá
_prev_volume: Dict[str, float] = {}      # để tính volume spike highlight

# ========= Formatter =========
def fmt_vnd_price(x: float) -> str:
    """VND: >=1 -> số nguyên; <1 -> 4 chữ số thập phân (không ký hiệu ₫)."""
    if x >= 1:
        return f"{int(round(x)):,.0f}"
    return f"{x:.4f}"

def fmt_vnd_amount(x: float) -> str:
    """Khối lượng/giá trị quy đổi VND: luôn số nguyên có nhóm nghìn + ' VND'."""
    return f"{int(round(x)):,.0f} VND"

def fmt_usd_price(x: float) -> str:
    """USD: có nhóm nghìn, tối đa 4 chữ số thập phân (tự cắt đuôi 0)."""
    return f"{x:,.4f}".rstrip("0").rstrip(".")

def fmt_usd_amount_int(x: float) -> str:
    """Khối lượng USDT: số nguyên có nhóm nghìn + ' USDT'."""
    return f"{int(round(x)):,.0f} USDT"
# =============================

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

def _fetch_tickers_live() -> List[dict]:
    tick = _get_json(MEXC_TICKER_URL)
    items = []
    if isinstance(tick, dict) and tick.get("success"):
        arr = tick.get("data") or []
    elif isinstance(tick, list):
        arr = tick
    else:
        arr = []

    for it in arr:
        sym = it.get("symbol") or it.get("instrument_id")
        if not sym or not str(sym).endswith("_USDT"):
            continue
        try: last = float(it.get("lastPrice") or it.get("last") or it.get("price") or 0)
        except: last = 0.0
        try: qvol = float(it.get("quoteVol") or it.get("amount24") or it.get("turnover") or 0)
        except: qvol = 0.0
        try:
            raw = it.get("riseFallRate") or it.get("changeRate") or it.get("percent") or 0
            chg = float(raw) * (100.0 if abs(float(raw)) < 1.0 else 1.0)
        except:
            chg = 0.0

        items.append({
            "symbol": sym,                 # BTC_USDT
            "lastPrice": last,             # USDT
            "volumeQuote": qvol,           # USDT
            "change24h_pct": chg,          # %
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
                try: fr = float(it.get("fundingRate") or it.get("rate") or it.get("value") or 0)
                except: fr = 0.0
                fmap[s] = fr * 100.0  # %
    return fmap

def top_symbols(unit: str = "VND", topn: int = 30):
    """LIVE-ONLY: nếu không lấy được dữ liệu -> trả ([], False, rate)"""
    items = _fetch_tickers_live()
    if not items:
        return [], False, usd_vnd_rate()

    fmap = _fetch_funding_live()
    rate = usd_vnd_rate()
    items.sort(key=lambda d: d.get("volumeQuote", 0.0), reverse=True)
    sel = items[:topn]
    for d in sel:
        d["fundingRate"] = fmap.get(d["symbol"], 0.0)
        if unit == "VND":
            d["lastPriceVND"] = d["lastPrice"] * rate
            d["volumeValueVND"] = d["volumeQuote"] * rate
        else:
            d["lastPriceVND"] = None
            d["volumeValueVND"] = None
    return sel, True, rate

def pick_scalping_signals(unit: str, n_scalp=5):
    coins, live, rate = top_symbols(unit=unit, topn=30)
    if not live or not coins:
        return [], [], live, rate

    # chọn 5 mã từ top 12 (0,2,4,6,8)
    pool = coins[:12]
    idxs = [0, 2, 4, 6, 8]
    chosen = [pool[i] for i in idxs if i < len(pool)]

    # nổi bật: funding lệch mạnh hoặc volume spike
    highlights = []
    global _prev_volume
    for c in coins[:10]:
        sym = c["symbol"]
        pv = _prev_volume.get(sym, 0.0)
        spike = (pv > 0 and c["volumeQuote"]/pv >= ALERT_VOLUME_SPIKE)
        if abs(c.get("fundingRate", 0.0)) >= ALERT_FUNDING_ABS * 100 or spike:
            tag = f"{sym} f={c.get('fundingRate',0):.3f}%"
            if spike:
                tag += f" • Vol x{(c['volumeQuote']/max(1.0,pv)):.1f}"
            highlights.append(tag)
    _prev_volume = {c["symbol"]: c["volumeQuote"] for c in coins}

    signals = []
    for rank, c in enumerate(chosen):
        change = c.get("change24h_pct", 0.0)
        funding = c.get("fundingRate", 0.0)
        side = "LONG" if (change >= 0 and funding > -0.02) else "SHORT"

        base = max(0, 100 - rank*3)
        trend = min(40, abs(change))
        fr = min(20, abs(funding)*2)
        strength = int(max(30, min(95, base*0.5 + trend + fr)))

        if unit == "VND":
            px = c["lastPriceVND"]
            tp = px * (1.006 if side == "LONG" else 0.994)
            sl = px * (0.992 if side == "LONG" else 1.008)
            entry = fmt_vnd_price(px)
            tp_s  = fmt_vnd_price(tp)
            sl_s  = fmt_vnd_price(sl)
            unit_tag = "VND"
            volq = fmt_vnd_amount(c["volumeValueVND"])
        else:
            px = c["lastPrice"]
            tp = px * (1.006 if side == "LONG" else 0.994)
            sl = px * (0.992 if side == "LONG" else 1.008)
            entry = fmt_usd_price(px) + " USDT"
            tp_s  = fmt_usd_price(tp) + " USDT"
            sl_s  = fmt_usd_price(sl) + " USDT"
            unit_tag = "USD"
            volq = fmt_usd_amount_int(c["volumeQuote"])

        reason = f"Funding={funding:+.3f}%, VolQ≈{volq}, Δ24h={change:+.2f}%"
        signals.append({
            "token": c["symbol"].replace("_USDT",""),
            "side": side,
            "type": "Scalping",
            "orderType": "Market",
            "entry": entry,
            "tp": tp_s,
            "sl": sl_s,
            "strength": strength,
            "reason": reason,
            "unit": unit_tag
        })

    return signals, highlights, live, rate
