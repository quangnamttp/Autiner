# bots/telegram_bot/mexc_api.py
import time
import math
import random
import requests
from collections import deque
from typing import List, Dict, Tuple

from settings import (
    MEXC_TICKER_URL,    # https://contract.mexc.com/api/v1/contract/ticker
    MEXC_FUNDING_URL,   # https://contract.mexc.com/api/v1/contract/funding_rate/last-rate  (hoặc fundingRate)
    MEXC_KLINES_URL,    # https://contract.mexc.com/api/v1/contract/kline?symbol={sym}&interval=Min1&limit=120
    USDVND_URL,
    HTTP_TIMEOUT, HTTP_RETRY,
    FX_CACHE_TTL,
    # smart params
    VOL24H_FLOOR, BREAK_VOL_MULT, FUNDING_ABS_LIM,
    ATR_ENTRY_K, ATR_ZONE_K, ATR_TP_K, ATR_SL_K,
    TTL_MINUTES, TRAIL_START_K, TRAIL_STEP_K,
    DIVERSITY_POOL_TOPN, SAME_PRICE_EPS, REPEAT_BONUS_DELTA,
)

# ===== Session & cache =====
_session = requests.Session()
_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124 Safari/537.36"}

_last_fx = {"ts": 0.0, "rate": 24500.0}
_prev_volume: Dict[str, float] = {}     # symbol -> last quote volume (USDT)
_hist_px: Dict[str, deque]  = {}        # symbol -> deque of last USD prices (3 slots ~ 90m)
_last_batch: set[str] = set()           # symbols picked last batch

# ===== Auto denomination (giống ONUS) =====
from .denom import auto_denom

# ===== Formatter =====
def fmt_price_vnd(p: float) -> str:
    """
    VND giống ONUS:
      - >= 100_000        : 0 chữ số thập phân
      - >= 1_000 < 100_000: 2 chữ số thập phân
      - < 1_000           : 4 chữ số thập phân
    Kèm phân tách nghìn bằng dấu phẩy (Telegram sẽ hiển thị).
    """
    p = float(p or 0.0)
    if p >= 100_000:
        return f"{p:,.0f}"
    elif p >= 1_000:
        return f"{p:,.2f}"
    else:
        return f"{p:,.4f}"

def fmt_price_usd(p: float) -> str:
    s = f"{float(p or 0.0):.4f}".rstrip("0").rstrip(".")
    return s if s else "0"

def fmt_amount_int(x: float, unit: str) -> str:
    return f"{float(x or 0.0):,.0f} {unit}"

# ===== HTTP helper =====
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

# ===== Fetch live =====
def _fetch_tickers_live() -> List[dict]:
    """
    Chuẩn hoá:
    {
      symbol: "BTC_USDT",
      lastPrice: <USD>,            # sẽ auto-denom sau
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
        # giá USD gốc
        try: last = float(it.get("lastPrice") or it.get("last") or it.get("price") or 0.0)
        except: last = 0.0
        # quote volume (USDT)
        try: qvol = float(it.get("quoteVol") or it.get("amount24") or it.get("turnover") or 0.0)
        except: qvol = 0.0
        # % đổi 24h
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

def _fetch_klines_min1(sym: str) -> List[dict]:
    """
    Lấy kline 1m để tính EMA/ATR/RSI đơn giản cho tín hiệu.
    Trả về list dict có 'c'(close), 'h','l','v' nếu API có.
    """
    url = MEXC_KLINES_URL.format(sym=sym)
    js = _get_json(url)
    out = []
    if isinstance(js, dict) and js.get("success") and isinstance(js.get("data"), list):
        data = js["data"]
    elif isinstance(js, list):
        data = js
    else:
        data = []
    for k in data:
        # MEXC kline response có thể dạng list; chuẩn hoá:
        # [time, open, high, low, close, volume, ...]
        if isinstance(k, list) and len(k) >= 6:
            try:
                close = float(k[4]); high = float(k[2]); low = float(k[3]); vol = float(k[5])
                out.append({"c": close, "h": high, "l": low, "v": vol})
            except:
                continue
        elif isinstance(k, dict):
            try:
                close = float(k.get("close") or k.get("c") or 0.0)
                high  = float(k.get("high")  or k.get("h") or 0.0)
                low   = float(k.get("low")   or k.get("l") or 0.0)
                vol   = float(k.get("volume") or k.get("v") or 0.0)
                out.append({"c": close, "h": high, "l": low, "v": vol})
            except:
                continue
    return out[-120:]  # 120 nến 1m

# ===== Chỉ báo cơ bản =====
def ema(series: List[float], period: int) -> float:
    if not series or len(series) < period:
        return 0.0
    k = 2/(period+1)
    e = series[-period]
    for x in series[-period+1:]:
        e = x*k + e*(1-k)
    return e

def rsi(series: List[float], period: int = 14) -> float:
    if not series or len(series) < period+1:
        return 50.0
    gains = []
    losses = []
    for i in range(-period, 0):
        diff = series[i] - series[i-1]
        if diff >= 0: gains.append(diff)
        else: losses.append(-diff)
    avg_gain = sum(gains)/period if gains else 0.0
    avg_loss = sum(losses)/period if losses else 0.0
    if avg_loss == 0:
        return 70.0
    rs = avg_gain/avg_loss
    return 100 - (100/(1+rs))

def atr(hlc: List[Tuple[float,float,float]], period: int = 14) -> float:
    if len(hlc) < period+1:
        return 0.0
    trs = []
    prev_close = hlc[-period-1][2]
    for i in range(-period, 0):
        h, l, c = hlc[i]
        tr = max(h - l, abs(h - prev_close), abs(l - prev_close))
        trs.append(tr)
        prev_close = c
    return sum(trs)/period if trs else 0.0

# ===== Snapshot thị trường (đã auto-denom + VND/USD) =====
def market_snapshot(unit: str = "VND", topn: int = 40) -> Tuple[List[dict], bool, float]:
    """
    Trả (coins, live, rate). Mỗi phần tử:
      - symbol (gốc), displaySymbol (đổi nếu auto-denom)
      - lastPrice (USD sau denom), lastPriceVND (nếu unit=VND)
      - volumeQuote (USDT), volumeValueVND (nếu unit=VND)
      - change24h_pct, fundingRate (%)
    """
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

# ===== Softmax helper =====
def _softmax(xs):
    if not xs: return []
    m = max(xs)
    exps = [math.exp(x - m) for x in xs]
    s = sum(exps) or 1.0
    return [e/s for e in exps]

def _momentum_features(sym: str, px_now_usd: float) -> Tuple[float, float]:
    """
    Ước lượng r30 & r60 dựa trên lịch sử slot (deque 3 phần tử).
    """
    dq = _hist_px.get(sym)
    if not dq or len(dq) < 2 or dq[-2] <= 0 or px_now_usd <= 0:
        return 0.0, 0.0
    r30 = (px_now_usd - dq[-2]) / dq[-2] * 100.0
    if len(dq) >= 3 and dq[-3] > 0:
        r60 = (px_now_usd - dq[-3]) / dq[-3] * 100.0
    else:
        r60 = 0.0
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
    if r30 > 0.0 and (funding >= -0.02 or change24h >= 0):
        return "LONG"
    if r30 < 0.0 and (funding <= 0.02 or change24h <= 0):
        return "SHORT"
    return "LONG" if change24h >= 0 else "SHORT"

# ===== Chọn tín hiệu linh hoạt =====
def smart_pick_signals(unit: str, n_scalp=5):
    # Khai báo global NGAY ĐẦU HÀM để tránh lỗi "used prior to global"
    global _last_batch, _prev_volume

    coins, live, rate = market_snapshot(unit="USD", topn=DIVERSITY_POOL_TOPN)
    if not live or not coins:
        return [], [], live, rate

    # Lọc theo volume sàn & động lượng ngắn hạn
    pool = []
    prev_vol_map = {c["symbol"]: _prev_volume.get(c["symbol"], 0.0) for c in coins}
    for idx, c in enumerate(coins):
        if c.get("volumeQuote", 0.0) < VOL24H_FLOOR:
            continue
        score, r30, r60 = _score_coin(idx, c, prev_vol_map.get(c["symbol"], 0.0))
        # Đảm bảo có chuyển động ý nghĩa (>= ~0.2% trong 30’)
        if abs(r30) < 0.2:
            continue
        pool.append((score, r30, r60, idx, c))

    if not pool:
        return [], [], live, rate

    # Nếu lặp lại từ batch trước, yêu cầu score vượt trội
    scores_only = [p[0] for p in pool]
    median = sorted(scores_only)[len(scores_only)//2]
    keep = []
    for p in pool:
        score, r30, r60, idx, c = p
        if c["symbol"] in _last_batch:
            if score >= median + REPEAT_BONUS_DELTA:
                keep.append(p)
        else:
            keep.append(p)
    if not keep:
        keep = pool

    # Softmax để vừa ưu tiên vừa đa dạng
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

    # Dựng tín hiệu (VND hoặc USD)
    signals = []
    highlights = []
    now_rate = usd_vnd_rate()

    for rank, (score, r30, r60, idx, c) in enumerate(picked):
        change  = c.get("change24h_pct", 0.0)
        funding = c.get("fundingRate", 0.0)
        side = _side_from_momo_funding(r30, change, funding)

        # Strength
        strength = int(max(35, min(95, 65 + score*8 - rank*3)))

        # Lấy kline 1m để tính EMA/RSI/ATR -> quyết định Market/Limit và giải thích
        kl = _fetch_klines_min1(c["symbol"])
        closes = [k["c"] for k in kl] if kl else []
        highs  = [k["h"] for k in kl] if kl else []
        lows   = [k["l"] for k in kl] if kl else []
        vols   = [k["v"] for k in kl] if kl else []

        ema9  = ema(closes, 9)  if closes else 0.0
        ema21 = ema(closes, 21) if closes else 0.0
        rsi14 = rsi(closes, 14) if closes else 50.0
        atr14 = atr(list(zip(highs, lows, closes)), 14) if (highs and lows and closes) else 0.0

        # Ước lượng volume hiện tại so với MA20Vol
        ma20vol = sum(vols[-20:])/20.0 if len(vols) >= 20 else (sum(vols)/max(1,len(vols)) if vols else 0.0)
        cur_vol = vols[-1] if vols else 0.0
        vol_ok = (ma20vol > 0 and cur_vol >= BREAK_VOL_MULT * ma20vol)

        # Quyết định MARKET/LIMIT
        is_market = (vol_ok and abs(funding) <= FUNDING_ABS_LIM)
        order_type = "Market" if is_market else "Limit"

        # Tên hiển thị & giá hiện tại (USD sau auto-denom), rồi quy đổi nếu cần
        disp, adj_usd, mul = auto_denom(c["symbol"], c["lastPrice"], now_rate)
        if unit == "VND":
            px = adj_usd * now_rate
            if atr14 <= 0:
                # fallback nhỏ nếu thiếu ATR
                atr_px = max(px*0.002, 1.0)
            else:
                atr_px = atr14 * now_rate
            if side == "LONG":
                entry_raw = px if is_market else px - ATR_ENTRY_K*atr_px
                tp_raw = entry_raw + ATR_TP_K*atr_px
                sl_raw = entry_raw - ATR_SL_K*atr_px
            else:
                entry_raw = px if is_market else px + ATR_ENTRY_K*atr_px
                tp_raw = entry_raw - ATR_TP_K*atr_px
                sl_raw = entry_raw + ATR_SL_K*atr_px

            entry = fmt_price_vnd(entry_raw) + " VND"
            tp_s  = fmt_price_vnd(tp_raw)    + " VND"
            sl_s  = fmt_price_vnd(sl_raw)    + " VND"
            unit_tag = "VND"
            volq = fmt_amount_int(c.get("volumeQuote", 0.0) * now_rate, "VND")
        else:
            px = adj_usd
            if atr14 <= 0:
                atr_px = max(px*0.002, 0.0001)
            else:
                atr_px = atr14
            if side == "LONG":
                entry_raw = px if is_market else px - ATR_ENTRY_K*atr_px
                tp_raw = entry_raw + ATR_TP_K*atr_px
                sl_raw = entry_raw - ATR_SL_K*atr_px
            else:
                entry_raw = px if is_market else px + ATR_ENTRY_K*atr_px
                tp_raw = entry_raw - ATR_TP_K*atr_px
                sl_raw = entry_raw + ATR_SL_K*atr_px

            entry = fmt_price_usd(entry_raw) + " USDT"
            tp_s  = fmt_price_usd(tp_raw)    + " USDT"
            sl_s  = fmt_price_usd(sl_raw)    + " USDT"
            unit_tag = "USD"
            volq = fmt_amount_int(c.get("volumeQuote", 0.0), "USDT")

        # Giải thích lý do (ngắn gọn, dễ hiểu)
        trend_txt = "Giá trên EMA9>EMA21" if (ema9 > 0 and ema21 > 0 and closes and closes[-1] > ema9 > ema21) else \
                    "Giá dưới EMA9<EMA21" if (ema9 > 0 and ema21 > 0 and closes and closes[-1] < ema9 < ema21) else \
                    "Giá gần EMA"

        rsi_txt = "RSI>55 (xung lực tốt)" if rsi14 >= 55 else ("RSI<45 (yếu)" if rsi14 <= 45 else "RSI trung tính")
        vol_txt = "Vol tăng" if vol_ok else "Vol bình thường"
        fund_txt= f"Funding {funding:+.3f}%"

        reason = f"{trend_txt}, {rsi_txt}, {vol_txt}, {fund_txt}. r30={r30:+.2f}%"
        token = disp

        signals.append({
            "token": token,
            "side": side,
            "type": "Scalping",
            "orderType": order_type,
            "entry": entry,
            "tp": tp_s,
            "sl": sl_s,
            "strength": int(max(35, min(95, strength))),
            "reason": reason,
            "unit": unit_tag
        })

        # cập nhật lịch sử để tính r30/r60 slot sau
        dq = _hist_px.setdefault(c["symbol"], deque(maxlen=3))
        dq.append(float(adj_usd))

    # LƯU Ý: cập nhật global sau khi đã khai báo global đầu hàm
    _last_batch = {c["symbol"] for (_,_,_,_,c) in picked}
    _prev_volume = {c["symbol"]: c.get("volumeQuote", 0.0) for c in coins}

    return signals, highlights, live, now_rate
