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
                return data.get("data", [])
    except Exception as e:
        print(f"[ERROR] get_all_futures: {e}")
        print(traceback.format_exc())
        return []

# =============================
# Lấy tỷ giá USDT/VND
# =============================
async def get_usdt_vnd_rate() -> float:
    url = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"
    payload = {"asset": "USDT","fiat": "VND","merchantCheck": False,"page": 1,"rows": 10,"tradeType": "SELL"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=15) as resp:
                data = await resp.json()
                advs = data.get("data", [])
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
# Chỉ báo kỹ thuật
# =============================
def calculate_indicators(klines):
    try:
        closes = np.array([float(k[4]) for k in klines], dtype=float)
        if len(closes) < 20:
            return {}

        # EMA
        ema20 = np.mean(closes[-20:])
        ema50 = np.mean(closes[-50:]) if len(closes) >= 50 else ema20

        # RSI(14)
        deltas = np.diff(closes)
        ups = deltas[deltas > 0].sum() / 14 if len(deltas) >= 14 else 0
        downs = -deltas[deltas < 0].sum() / 14 if len(deltas) >= 14 else 0
        rs = (ups / downs) if downs != 0 else 0
        rsi = 100 - (100 / (1 + rs)) if rs != 0 else 50

        # MACD
        ema12 = np.mean(closes[-12:])
        ema26 = np.mean(closes[-26:]) if len(closes) >= 26 else ema12
        macd = ema12 - ema26
        signal = np.mean([ema12, ema26])
        macd_signal = "bullish" if macd > signal else "bearish"

        # Bollinger Bands
        mid = np.mean(closes[-20:])
        std = np.std(closes[-20:])
        upper = mid + 2 * std
        lower = mid - 2 * std
        last = closes[-1]
        if last >= upper:
            bb_status = "gần biên trên"
        elif last <= lower:
            bb_status = "gần biên dưới"
        else:
            bb_status = "trong dải"

        return {"RSI": round(rsi,2), "EMA20": round(ema20,2), "EMA50": round(ema50,2),
                "MACD": macd_signal, "Bollinger": bb_status}
    except Exception as e:
        print(f"[ERROR] calculate_indicators: {e}")
        return {}

# =============================
# AI phân tích coin (có fallback chỉ báo)
# =============================
async def analyze_coin(symbol: str, price: float, change_pct: float, market_trend: dict):
    try:
        klines = await get_kline(symbol, "Min15", 100)
        indicators = calculate_indicators(klines) if klines else {}

        # AI
        OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY", "")
        if OPENROUTER_KEY:
            try:
                async with aiohttp.ClientSession() as session:
                    headers = {"Authorization": f"Bearer {OPENROUTER_KEY}", "Content-Type": "application/json"}
                    payload = {
                        "model": os.getenv("OPENROUTER_MODEL", "deepseek-chat-v3-0324:free"),
                        "messages": [
                            {"role": "system", "content": "Bạn là chuyên gia crypto. Luôn trả JSON {\"side\":\"LONG/SHORT\",\"strength\":% ,\"reason\":\"...\"}"},
                            {"role": "user", "content": f"Phân tích {symbol}, giá={price}, biến động={change_pct}%, xu hướng={market_trend}, chỉ báo={indicators}"}
                        ]
                    }
                    async with session.post(os.getenv("OPENROUTER_API_URL","https://openrouter.ai/api/v1/chat/completions"),
                                             headers=headers, data=json.dumps(payload), timeout=50) as resp:
                        data = await resp.json()
                        if "choices" in data:
                            ai_text = data["choices"][0]["message"]["content"]
                            result = json.loads(ai_text)
                            return {"side": result["side"], "strength": result["strength"], "reason": result["reason"]}
            except Exception as e:
                print(f"[AI ERROR] {e}")

        # Fallback: phân tích bằng chỉ báo
        if not indicators:
            return {"side":"LONG", "strength":60, "reason":"Không có dữ liệu nến đủ"}

        side = "LONG"
        strength = 60
        reasons = []

        if indicators["RSI"] > 70:
            side = "SHORT"; strength = 75; reasons.append(f"RSI={indicators['RSI']} quá mua")
        elif indicators["RSI"] < 30:
            side = "LONG"; strength = 75; reasons.append(f"RSI={indicators['RSI']} quá bán")

        if indicators["MACD"] == "bullish":
            if side=="LONG": strength+=10
            reasons.append("MACD bullish")
        else:
            if side=="SHORT": strength+=10
            reasons.append("MACD bearish")

        if price > indicators["EMA20"] and price > indicators["EMA50"]:
            reasons.append("Giá trên EMA20/EMA50 → xu hướng tăng")
        elif price < indicators["EMA20"] and price < indicators["EMA50"]:
            reasons.append("Giá dưới EMA20/EMA50 → xu hướng giảm")

        return {"side": side, "strength": min(strength,100), "reason": "; ".join(reasons)}

    except Exception as e:
        print(f"[ERROR] analyze_coin({symbol}): {e}")
        return {"side":"LONG","strength":60,"reason":"Fallback mặc định"}
