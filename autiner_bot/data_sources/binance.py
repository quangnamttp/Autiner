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
        data = await asyncio.to_thread(_get_json_sync, url, 25)
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
async def get_kline(symbol: str, interval="15m", limit=200):
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
# P2P USDT/VND
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
# Indicator helpers
# =============================
def calculate_indicators(klines):
    try:
        closes = np.array([float(k[4]) for k in klines], dtype=float)
        if len(closes) < 26:
            return {}

        # EMA
        ema20 = np.mean(closes[-20:]) if len(closes) >= 20 else closes[-1]
        ema50 = np.mean(closes[-50:]) if len(closes) >= 50 else closes[-1]

        # RSI (14)
        deltas = np.diff(closes)
        ups = deltas[deltas > 0].sum() / 14 if len(deltas) >= 14 else 0
        downs = -deltas[deltas < 0].sum() / 14 if len(deltas) >= 14 else 0
        rs = (ups / downs) if downs != 0 else 0
        rsi = 100 - (100 / (1 + rs)) if rs != 0 else 50

        # MACD
        ema12 = np.mean(closes[-12:]) if len(closes) >= 12 else closes[-1]
        ema26 = np.mean(closes[-26:]) if len(closes) >= 26 else closes[-1]
        macd = ema12 - ema26
        signal = np.mean([ema12, ema26])
        macd_signal = "bullish" if macd > signal else "bearish"

        # Bollinger
        mid = np.mean(closes[-20:]) if len(closes) >= 20 else closes[-1]
        std = np.std(closes[-20:]) if len(closes) >= 20 else 0
        upper = mid + 2 * std
        lower = mid - 2 * std
        last_close = closes[-1]
        if last_close >= upper:
            bb_status = "gần biên trên"
        elif last_close <= lower:
            bb_status = "gần biên dưới"
        else:
            bb_status = "trong dải"

        return {
            "RSI": round(rsi, 2),
            "MACD": macd_signal,
            "EMA20": round(ema20, 6),
            "EMA50": round(ema50, 6),
            "Bollinger": bb_status,
            "last_close": last_close
        }
    except Exception as e:
        print(f"[ERROR] calculate_indicators: {e}")
        return {}

# =============================
# Phân tích coin
# =============================
async def analyze_coin(symbol: str):
    try:
        klines = await get_kline(symbol, "15m", 200)
        indicators = calculate_indicators(klines) if klines else {}
        if not indicators:
            return {"side": "LONG", "strength": 50, "reason": "Không đủ dữ liệu"}

        rsi, macd = indicators["RSI"], indicators["MACD"]
        ema20, ema50 = indicators["EMA20"], indicators["EMA50"]

        score_long, score_short = 0, 0
        reasons = []

        # RSI
        if rsi < 30:
            score_long += 2; reasons.append("RSI thấp (<30) → quá bán")
        elif rsi > 70:
            score_short += 2; reasons.append("RSI cao (>70) → quá mua")

        # MACD
        if macd == "bullish":
            score_long += 1; reasons.append("MACD bullish")
        elif macd == "bearish":
            score_short += 1; reasons.append("MACD bearish")

        # EMA
        if ema20 > ema50:
            score_long += 1; reasons.append("EMA20 > EMA50 → xu hướng tăng")
        else:
            score_short += 1; reasons.append("EMA20 < EMA50 → xu hướng giảm")

        # Bollinger
        reasons.append(f"Bollinger: {indicators['Bollinger']}")

        side = "LONG" if score_long >= score_short else "SHORT"
        strength = 50 + 10 * abs(score_long - score_short)
        reason = "; ".join(reasons)

        return {"side": side, "strength": min(90, strength), "reason": reason}
    except Exception as e:
        print(f"[ERROR] analyze_coin({symbol}): {e}")
        return {"side": "LONG", "strength": 50, "reason": "Lỗi phân tích"}

# =============================
# Diagnose Binance (test route /diag)
# =============================
async def diagnose_binance():
    info = {"ping": None, "tickers_status": None, "tickers_len": None, "sample": None, "error": None}
    try:
        r1 = requests.get(f"{BINANCE_FUTURES_URL}/fapi/v1/ping", headers=HTTP_HEADERS, timeout=10)
        info["ping"] = r1.status_code

        r2 = requests.get(f"{BINANCE_FUTURES_URL}/fapi/v1/ticker/24hr", headers=HTTP_HEADERS, timeout=15)
        info["tickers_status"] = r2.status_code
        if r2.status_code == 200:
            js = r2.json()
            info["tickers_len"] = len(js) if isinstance(js, list) else None
            info["sample"] = js[0] if isinstance(js, list) and js else None
        else:
            info["error"] = r2.text[:300]
    except Exception as e:
        info["error"] = str(e)
    return info
