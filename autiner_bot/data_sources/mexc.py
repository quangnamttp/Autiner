import aiohttp
import traceback
import numpy as np

MEXC_BASE_URL = "https://contract.mexc.com"

# =============================
# Lấy toàn bộ coin Futures
# =============================
async def get_all_futures():
    try:
        url = f"{MEXC_BASE_URL}/api/v1/contract/ticker"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=15) as resp:
                data = await resp.json()
                return data.get("data", [])
    except Exception as e:
        print(f"[ERROR] get_all_futures: {e}")
        print(traceback.format_exc())
        return []

# =============================
# Lấy tỷ giá USDT/VND (Binance P2P)
# =============================
async def get_usdt_vnd_rate() -> float:
    url = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"
    payload = {"asset": "USDT","fiat": "VND","merchantCheck": False,"page": 1,"rows": 10,"tradeType": "SELL"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=15) as resp:
                data = await resp.json()
                advs = data.get("data", [])
                if not advs: return 0
                prices = [float(ad["adv"]["price"]) for ad in advs[:5] if "adv" in ad]
                return sum(prices)/len(prices) if prices else 0
    except Exception as e:
        print(f"[ERROR] get_usdt_vnd_rate: {e}")
        return 0

# =============================
# Lấy dữ liệu Kline
# =============================
async def get_kline(symbol: str, interval="Min15", limit=100):
    try:
        url = f"{MEXC_BASE_URL}/api/v1/contract/kline/{symbol}?interval={interval}&limit={limit}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=15) as resp:
                data = await resp.json()
                return data.get("data", [])
    except Exception as e:
        print(f"[ERROR] get_kline({symbol}): {e}")
        return []

# =============================
# Tính RSI, MACD, EMA, Bollinger
# =============================
def calculate_indicators(klines):
    closes = np.array([float(k[4]) for k in klines], dtype=float)
    if len(closes) < 20: return {}

    # EMA
    ema20 = np.mean(closes[-20:])
    ema50 = np.mean(closes[-50:]) if len(closes) >= 50 else np.mean(closes)

    # RSI
    deltas = np.diff(closes)
    ups = deltas[deltas > 0].sum()/14 if len(deltas) >= 14 else 0
    downs = -deltas[deltas < 0].sum()/14 if len(deltas) >= 14 else 0
    rs = (ups/downs) if downs != 0 else 0
    rsi = 100 - (100/(1+rs)) if rs != 0 else 50

    # MACD
    ema12 = np.mean(closes[-12:]) if len(closes) >= 12 else np.mean(closes)
    ema26 = np.mean(closes[-26:]) if len(closes) >= 26 else np.mean(closes)
    macd = ema12 - ema26
    signal = np.mean([ema12, ema26])
    macd_signal = "bullish" if macd > signal else "bearish"

    # Bollinger
    mid = np.mean(closes[-20:])
    std = np.std(closes[-20:])
    upper, lower = mid+2*std, mid-2*std
    last = closes[-1]
    if last >= upper: bb_status = "gần biên trên"
    elif last <= lower: bb_status = "gần biên dưới"
    else: bb_status = "trong dải"

    return {"RSI": round(rsi,2), "MACD": macd_signal,
            "EMA20": round(ema20,6), "EMA50": round(ema50,6),
            "Bollinger": bb_status}

# =============================
# Phân tích coin dựa chỉ báo (có lý do rõ ràng)
# =============================
async def analyze_coin(symbol: str, price: float, change_pct: float):
    klines = await get_kline(symbol, "Min15", 100)
    indicators = calculate_indicators(klines) if klines else {}
    if not indicators:
        return {"side": "LONG", "strength": 50, "reason": "Không đủ dữ liệu nến để phân tích"}

    rsi, macd, ema20, ema50, bb = indicators["RSI"], indicators["MACD"], indicators["EMA20"], indicators["EMA50"], indicators["Bollinger"]

    score_long, score_short = 0, 0
    reasons = []

    # RSI
    if rsi < 30:
        score_long += 2; reasons.append("RSI < 30 (quá bán, dễ hồi LONG)")
    elif rsi > 70:
        score_short += 2; reasons.append("RSI > 70 (quá mua, dễ chỉnh SHORT)")

    # MACD
    if macd == "bullish":
        score_long += 1; reasons.append("MACD bullish (xu hướng tăng)")
    else:
        score_short += 1; reasons.append("MACD bearish (xu hướng giảm)")

    # EMA
    if ema20 > ema50:
        score_long += 1; reasons.append("EMA20 > EMA50 (trend tăng)")
    else:
        score_short += 1; reasons.append("EMA20 < EMA50 (trend giảm)")

    # Tổng hợp
    side = "LONG" if score_long >= score_short else "SHORT"
    strength = 55 + 10*abs(score_long - score_short)  # dao động 55% - 85%
    reason = "; ".join(reasons) + f"; Bollinger={bb}"

    return {"side": side, "strength": min(90, strength), "reason": reason}
