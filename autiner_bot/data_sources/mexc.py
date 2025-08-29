import aiohttp
import traceback
import os
import json
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
                if not data or "data" not in data:
                    return []
                return data["data"]
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
                if not advs:
                    return 0
                prices = [float(ad["adv"]["price"]) for ad in advs[:5] if "adv" in ad]
                return sum(prices) / len(prices) if prices else 0
    except Exception as e:
        print(f"[ERROR] get_usdt_vnd_rate: {e}")
        return 0

# =============================
# Lấy dữ liệu Kline (nến)
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
    try:
        closes = np.array([float(k[4]) for k in klines], dtype=float)

        ema20 = np.mean(closes[-20:]) if len(closes) >= 20 else closes[-1]
        ema50 = np.mean(closes[-50:]) if len(closes) >= 50 else closes[-1]

        # RSI(14)
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

        # Bollinger Bands
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
            "Bollinger": bb_status
        }
    except Exception as e:
        print(f"[ERROR] calculate_indicators: {e}")
        return {}

# =============================
# AI phân tích coin (KHÔNG fallback)
# =============================
async def analyze_coin(symbol: str, price: float, change_pct: float, market_trend: dict):
    try:
        klines = await get_kline(symbol, "Min15", 100)
        indicators = calculate_indicators(klines) if klines else {}

        if not indicators:
            indicators = {"RSI": "N/A", "MACD": "N/A", "EMA20": "N/A", "EMA50": "N/A", "Bollinger": "N/A"}

        OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY", "")
        if not OPENROUTER_KEY:
            print("[AI ERROR] Chưa có OPENROUTER_API_KEY")
            return None

        # Feed cho AI
        msg = (
            f"Phân tích coin {symbol}:\n"
            f"- Giá hiện tại: {price}\n"
            f"- Biến động 24h: {change_pct}%\n"
            f"- Xu hướng thị trường: {market_trend}\n"
            f"- Chỉ báo kỹ thuật: {indicators}\n\n"
            f"Hãy đưa ra khuyến nghị LONG hoặc SHORT."
        )

        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {OPENROUTER_KEY}", "Content-Type": "application/json"}
            payload = {
                "model": os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.1-8b-instruct:free"),
                "messages": [
                    {"role": "system", "content": "Bạn là chuyên gia crypto. Luôn trả JSON: {\"side\":\"LONG/SHORT\",\"strength\": %, \"reason\":\"ngắn gọn\"}"},
                    {"role": "user", "content": msg}
                ]
            }
            async with session.post(os.getenv("OPENROUTER_API_URL","https://openrouter.ai/api/v1/chat/completions"),
                                     headers=headers, data=json.dumps(payload), timeout=50) as resp:
                data = await resp.json()
                if "choices" not in data:
                    print("[AI ERROR] Không có choices:", data)
                    return None

                ai_text = data["choices"][0]["message"]["content"]

                try:
                    result = json.loads(ai_text)
                    strength = max(50, min(100, result.get("strength", 70)))
                    return {
                        "side": result.get("side", "LONG"),
                        "strength": strength,
                        "reason": result.get("reason", "AI phân tích từ chỉ báo")
                    }
                except Exception as e:
                    print("[AI ERROR] JSON parse fail:", ai_text)
                    return None
    except Exception as e:
        print(f"[ERROR] analyze_coin({symbol}): {e}")
        return None
