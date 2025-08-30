import aiohttp
import traceback
import numpy as np

BINANCE_FUTURES_URL = "https://fapi.binance.com"
BINANCE_P2P_URL = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"


# =============================
# Lấy toàn bộ coin Futures (Binance)
# =============================
async def get_all_futures():
    try:
        url = f"{BINANCE_FUTURES_URL}/fapi/v1/ticker/24hr"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=15) as resp:
                data = await resp.json()
                return data if isinstance(data, list) else []
    except Exception as e:
        print(f"[ERROR] get_all_futures: {e}")
        print(traceback.format_exc())
        return []


# =============================
# Lấy tỷ giá USDT/VND (Binance P2P)
# =============================
async def get_usdt_vnd_rate() -> float:
    payload = {"asset": "USDT", "fiat": "VND", "merchantCheck": False,
               "page": 1, "rows": 10, "tradeType": "SELL"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(BINANCE_P2P_URL, json=payload, timeout=15) as resp:
                data = await resp.json()
                advs = data.get("data", [])
                if not advs:
                    return 0
                prices = [float(ad["adv"]["price"]) for ad in advs[:5] if "adv" in ad]
                return sum(prices) / len(prices) if prices else 0
    except Exception as e:
        print(f"[ERROR] get_usdt_vnd_rate: {e}")
        return 0


# =============================
# Lấy dữ liệu Kline (nến) từ Binance Futures
# =============================
async def get_kline(symbol: str, interval="15m", limit=200):
    try:
        url = f"{BINANCE_FUTURES_URL}/fapi/v1/klines?symbol={symbol}&interval={interval}&limit={limit}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=15) as resp:
                data = await resp.json()
                return data if isinstance(data, list) else []
    except Exception as e:
        print(f"[ERROR] get_kline({symbol}): {e}")
        return []


# =============================
# Tính RSI, MACD, EMA, Bollinger
# =============================
def calculate_indicators(klines):
    try:
        closes = np.array([float(k[4]) for k in klines], dtype=float)

        ema20 = np.mean(closes[-20:]) if len(closes) >= 20 else closes[-1]
        ema50 = np.mean(closes[-50:]) if len(closes) >= 50 else closes[-1]

        deltas = np.diff(closes)
        ups = deltas[deltas > 0].sum() / 14 if len(deltas) >= 14 else 0
        downs = -deltas[deltas < 0].sum() / 14 if len(deltas) >= 14 else 0
        rs = (ups / downs) if downs != 0 else 0
        rsi = 100 - (100 / (1 + rs)) if rs != 0 else 50

        ema12 = np.mean(closes[-12:]) if len(closes) >= 12 else closes[-1]
        ema26 = np.mean(closes[-26:]) if len(closes) >= 26 else closes[-1]
        macd = ema12 - ema26
        signal = np.mean([ema12, ema26])
        macd_signal = "bullish" if macd > signal else "bearish"

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
            "last_close": closes[-1]
        }
    except Exception as e:
        print(f"[ERROR] calculate_indicators: {e}")
        return {}


# =============================
# Phân tích coin bằng chỉ báo
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
