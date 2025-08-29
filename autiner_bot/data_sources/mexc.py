import aiohttp
import os
import json
import traceback
import numpy as np

MEXC_BASE_URL = "https://contract.mexc.com"

# =============================
# Lấy dữ liệu Kline (nến 1m)
# =============================
async def get_klines(symbol: str, limit: int = 120):
    url = f"{MEXC_BASE_URL}/api/v1/contract/kline/{symbol}?interval=Min1&limit={limit}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=15) as resp:
                data = await resp.json()
                if "data" not in data:
                    return []
                return data["data"]
    except Exception as e:
        print(f"[ERROR] get_klines({symbol}): {e}")
        return []

# =============================
# Các chỉ báo kỹ thuật
# =============================
def calculate_indicators(klines):
    try:
        closes = np.array([float(k[4]) for k in klines])  # close price
        if len(closes) < 50:
            return {}

        # RSI(14)
        delta = np.diff(closes)
        gain = np.where(delta > 0, delta, 0)
        loss = np.where(delta < 0, -delta, 0)
        avg_gain = np.mean(gain[-14:])
        avg_loss = np.mean(loss[-14:]) + 1e-9
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        # EMA20 & EMA50
        def ema(arr, period):
            k = 2 / (period + 1)
            ema_vals = [np.mean(arr[:period])]
            for price in arr[period:]:
                ema_vals.append(price * k + ema_vals[-1] * (1 - k))
            return ema_vals[-1]

        ema20 = ema(closes, 20)
        ema50 = ema(closes, 50)

        # MACD (12,26,9)
        def ema_series(arr, period):
            k = 2 / (period + 1)
            ema_vals = [np.mean(arr[:period])]
            for price in arr[period:]:
                ema_vals.append(price * k + ema_vals[-1] * (1 - k))
            return np.array(ema_vals)

        ema12 = ema_series(closes, 12)
        ema26 = ema_series(closes, 26)
        macd_line = ema12[-1] - ema26[-1]
        signal_line = np.mean(macd_line)  # simple approx
        macd_status = "cắt lên" if macd_line > signal_line else "cắt xuống"

        # Bollinger Bands (20,2)
        sma20 = np.mean(closes[-20:])
        std20 = np.std(closes[-20:])
        upper = sma20 + 2 * std20
        lower = sma20 - 2 * std20
        bb_position = "gần biên trên" if closes[-1] > sma20 else "gần biên dưới"

        return {
            "RSI": round(rsi, 2),
            "EMA20": round(ema20, 4),
            "EMA50": round(ema50, 4),
            "MACD": round(macd_line, 4),
            "MACD_status": macd_status,
            "Bollinger": bb_position,
            "Upper": round(upper, 4),
            "Lower": round(lower, 4),
        }
    except Exception as e:
        print(f"[ERROR] calculate_indicators: {e}")
        return {}

# =============================
# AI phân tích coin (DeepSeek)
# =============================
async def analyze_coin(symbol: str, price: float, change_pct: float, market_trend: dict):
    try:
        klines = await get_klines(symbol)
        if not klines:
            return None
        indicators = calculate_indicators(klines)

        OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY", "")
        if not OPENROUTER_KEY:
            print("[AI ERROR] Chưa có OPENROUTER_API_KEY")
            return None

        prompt = f"""
Phân tích coin {symbol}:
- Giá hiện tại: {price}
- Biến động 24h: {change_pct}%
- Xu hướng thị trường: {market_trend}
- RSI(14): {indicators.get('RSI')}
- MACD: {indicators.get('MACD')} ({indicators.get('MACD_status')})
- EMA20: {indicators.get('EMA20')}, EMA50: {indicators.get('EMA50')}
- Bollinger Bands: {indicators.get('Bollinger')} (Upper={indicators.get('Upper')}, Lower={indicators.get('Lower')})

Trả về đúng JSON:
{{"side": "LONG/SHORT", "strength": %, "reason": "ngắn gọn"}}
"""

        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {OPENROUTER_KEY}", "Content-Type": "application/json"}
            payload = {
                "model": os.getenv("OPENROUTER_MODEL", "deepseek-chat-v3-0324:free"),
                "messages": [
                    {"role": "system", "content": "Bạn là chuyên gia phân tích crypto."},
                    {"role": "user", "content": prompt}
                ]
            }
            async with session.post(os.getenv("OPENROUTER_API_URL","https://openrouter.ai/api/v1/chat/completions"),
                                    headers=headers, data=json.dumps(payload), timeout=40) as resp:
                data = await resp.json()
                if "choices" not in data:
                    print("[AI ERROR]", data)
                    return None

                ai_text = data["choices"][0]["message"]["content"]
                try:
                    result = json.loads(ai_text)
                except:
                    print("[AI JSON ERROR]:", ai_text)
                    return None

                strength = max(50, min(100, result.get("strength", 70)))
                return {
                    "side": result.get("side", "LONG"),
                    "strength": strength,
                    "reason": result.get("reason", "AI phân tích")
                }

    except Exception as e:
        print(f"[ERROR] analyze_coin({symbol}): {e}")
        print(traceback.format_exc())
        return None
