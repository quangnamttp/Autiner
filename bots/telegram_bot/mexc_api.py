# bots/telegram_bot/mexc_api.py
import time
import math
import random
import requests
from collections import deque
from typing import List, Dict, Tuple

from settings import (
    MEXC_TICKER_URL,    # ví dụ: https://contract.mexc.com/api/v1/contract/ticker
    MEXC_FUNDING_URL,   # ví dụ: https://contract.mexc.com/api/v1/contract/fundingRate
    USDVND_URL,         # ví dụ: https://open.er-api.com/v6/latest/USD
    HTTP_TIMEOUT, HTTP_RETRY,
    FX_CACHE_TTL,
)

# ===== Session & cache =====
_session = requests.Session()
_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124 Safari/537.36"}

_last_fx = {"ts": 0.0, "rate": 24500.0}
_prev_volume: Dict[str, float] = {}     # symbol -> last quote volume (USDT)
_hist_px: Dict[str, deque]  = {}        # symbol -> deque of last USD prices (3 slots ~ 90m)
_last_batch: set[str] = set()           # symbols picked last batch

# ===== SAFE DEFAULTS nếu settings.py thiếu các núm chỉnh =====
try:
    from settings import (
        DIVERSITY_POOL_TOPN,   # xét pool theo thanh khoản
        VOL_FLOOR_USDT_SMART,  # ngưỡng VolumeQuote (USDT) tối thiểu để xét
        MIN_ABS_R30_PCT,       # yêu cầu |r30| tối thiểu (% so với slot trước)
        SAME_PRICE_EPS,        # coi như đứng im nếu thay đổi nhỏ hơn eps
        REPEAT_BONUS_DELTA,    # nếu lặp mã cũ, yêu cầu score vượt median + delta
    )
except Exception:
    DIVERSITY_POOL_TOPN = 40
    VOL_FLOOR_USDT_SMART = 150_000
    MIN_ABS_R30_PCT = 0.25
    SAME_PRICE_EPS = 0.0005
    REPEAT_BONUS_DELTA = 0.40

# ===== Auto-denomination (gộp vào file này, KHÔNG cần denom.py) =====
def auto_denom(symbol: str, last_usd: float, vnd_rate: float) -> Tuple[str, float, float]:
    """
    Trả về (display_symbol, adjusted_usd_price, multiplier)
    - Nếu giá VND quá nhỏ -> nhân 1_000 hoặc 1_000_000 để dễ đọc (như ONUS)
    - Thêm hậu tố 1000/1M vào tên hiển thị
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

# ====== Formatter ======
def fmt_price_vnd(p: float) -> str:
    """
    VND giống ONUS:
      - >= 100_000        : 0 chữ số thập phân (2,345,678)
      - >= 1_000 < 100_000: 2 chữ số thập phân (12,345.67)
      - < 1_000           : 4 chữ số thập phân (296.6256)
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
    # Số lượng lớn: hiển thị số nguyên có phân cách nghìn
    return f"{float(x or 0.0):,.0f} {unit}"

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

# ====== Fetch live ======
def _fetch_tickers_live() -> List[dict]:
    """
    Chuẩn hoá một danh sách:
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
            # một số api trả 0.0123 (1.23%), chuẩn hoá:
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

# ====== Snapshot thị trường (đã auto-denom + VND/USD) ======
def market_snapshot(unit: str = "VND", topn: int = 40) -> Tuple[List[dict], bool, float]:
    """
    Trả (coins, live, rate). Mỗi phần tử đã có:
      - symbol (gốc), displaySymbol (đổi tên nếu auto-denom)
      - lastPrice (USD, sau denom), lastPriceVND (nếu unit=VND)
      - volumeQuote (USDT), volumeValueVND (nếu unit=VND)
      - change24h_pct, fundingRate (%)
    """
    items = _fetch_tickers_live()
    if not items:
        return [], False, usd_vnd_rate()
    fmap = _fetch_funding_live()
    rate = usd_vnd_rate()

    # sort theo thanh khoản và lấy topn
    items.sort(key=lambda d: d.get("volumeQuote", 0.0), reverse=True)
    items = items[:max(5, topn)]

    out = []
    for it in items:
        sym = it["symbol"]
        # auto denom để có tên hiển thị & giá USD đã nhân hệ số nếu cần
        disp, adj_usd, mul = auto_denom(sym, it["lastPrice"], rate)
        d = {
            "symbol": sym,
            "displaySymbol": disp,
            "lastPrice": adj_usd,                 # USD (đã auto-denom)
            "volumeQuote": it["volumeQuote"],     # USDT
            "change24h_pct": it["change24h_pct"], # %
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

# ====== Thuật toán chọn tín hiệu linh hoạt =====
def _softmax(xs):
    if not xs: return []
    m = max(xs)
    exps = [math.exp(x - m) for x in xs]
    s = sum(exps) or 1.0
    return [e/s for e in exps]

def _momentum_features(sym: str, px_now_usd: float) -> Tuple[float, float]:
    """
    Ước lượng r30 (so với giá slot trước ~30'), r60 (so với 2 slot trước).
    Nếu thiếu dữ liệu: (0, 0).
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

    # phạt đứng im vs slot trước
    still_pen = 0.0
    dq = _hist_px.get(c["symbol"])
    if dq and len(dq) >= 2:
        px_prev = dq[-2]
        if px_prev > 0 and abs(px_usd - px_prev) / px_prev < SAME_PRICE_EPS:
            still_pen = 0.7

    base = 1.0 / (idx_rank + 1.0)        # top volume cao hơn -> điểm gốc lớn
    dyn  = max(0.0, abs(r30)) / 2.0      # động lượng ngắn hạn
    acc  = accel / 2.0                   # gia tốc dương được thưởng
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

def smart_pick_signals(unit: str, n_scalp=5):
    # Dùng global TRƯỚC khi truy cập/ghi
    global _last_batch, _prev_volume

    coins, live, rate = market_snapshot(unit="USD", topn=DIVERSITY_POOL_TOPN)  # nền USD để tính động lượng nhất quán
    if not live or not coins:
        return [], [], live, rate

    # lọc sơ bộ theo volume và động lượng ước lượng r30
    pool = []
    prev_vol_map = {c["symbol"]: _prev_volume.get(c["symbol"], 0.0) for c in coins}
    for idx, c in enumerate(coins):
        if c.get("volumeQuote", 0.0) < VOL_FLOOR_USDT_SMART:
            continue
        score, r30, r60 = _score_coin(idx, c, prev_vol_map.get(c["symbol"], 0.0))
        if abs(r30) < MIN_ABS_R30_PCT:
            continue
        pool.append((score, r30, r60, idx, c))

    if not pool:
        return [], [], live, rate

    # Nếu lặp lại từ batch trước, yêu cầu score vượt trội
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

    # Softmax chọn n tín hiệu (ưu tiên mạnh nhưng vẫn đa dạng)
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

    # Dựng tín hiệu theo đơn vị bạn chọn (VND hoặc USD)
    signals = []
    highlights = []  # để dành tương lai nếu cần
    now_rate = usd_vnd_rate()

    for rank, (score, r30, r60, idx, c) in enumerate(picked):
        change  = c.get("change24h_pct", 0.0)
        funding = c.get("fundingRate", 0.0)
        side = _side_from_momo_funding(r30, change, funding)

        # Strength: dựa trên score + thứ tự trong picked
        strength = int(max(35, min(95, 65 + score*8 - rank*3)))

        # Tên hiển thị & giá hiện tại (auto-denom để hợp mắt như ONUS)
        disp, adj_usd, mul = auto_denom(c["symbol"], c["lastPrice"], now_rate)
        if unit == "VND":
            px = adj_usd * now_rate
            tp = px * (1.006 if side == "LONG" else 0.994)
            sl = px * (0.992 if side == "LONG" else 1.008)
            entry = fmt_price_vnd(px)
            tp_s  = fmt_price_vnd(tp)
            sl_s  = fmt_price_vnd(sl)
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

        token = disp  # tên sau auto-denom (vd: PEPE1000, SHIB1000, ...)
        accel = max(0.0, r30 - 0.5*r60)
        reason = f"r30={r30:+.2f}%, accel={accel:+.2f}%, funding={funding:+.3f}%, VolQ≈{volq}"

        signals.append({
            "token": token,
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

        # cập nhật lịch sử để tính r30/r60 slot sau (lưu theo USD để nhất quán)
        dq = _hist_px.setdefault(c["symbol"], deque(maxlen=3))
        dq.append(float(adj_usd))

    # lưu batch & prev volume cho vòng sau
    _last_batch = {c["symbol"] for (_,_,_,_,c) in picked}
    _prev_volume = {c["symbol"]: c.get("volumeQuote", 0.0) for c in coins}

    return signals, highlights, live, now_rate
