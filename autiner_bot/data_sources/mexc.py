import aiohttp
import os
import json
import traceback

MEXC_BASE_URL = "https://contract.mexc.com"

# =============================
# Lấy toàn bộ coin Futures từ MEXC (không lọc)
# =============================
async def get_all_futures():
    try:
        url = f"{MEXC_BASE_URL}/api/v1/contract/ticker"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=20) as resp:
                data = await resp.json()
                if not data or "data" not in data:
                    return []
                tickers = data["data"]

                coins = []
                for t in tickers:
                    if not t.get("symbol", "").endswith("_USDT"):
                        continue
                    coins.append({
                        "symbol": t["symbol"],
                        "lastPrice": float(t.get("lastPrice", 0)),
                        "volume": float(t.get("amount24", 0)),
                        "change_pct": float(t.get("riseFallRate", 0)) * 100
                    })
                return coins
    except Exception as e:
        print(f"[ERROR] get_all_futures: {e}")
        print(traceback.format_exc())
        return []

# =============================
# Lấy tỷ giá USDT/VND từ Binance
# =============================
async def get_usdt_vnd_rate() -> float:
    url = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"
    payload = {"asset": "USDT","fiat": "VND","merchantCheck": False,"page": 1,"rows": 10,"tradeType": "SELL"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=20) as resp:
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
# AI phân tích coin (DeepSeek / Copilot qua OpenRouter)
# =============================
async def analyze_coin(symbol: str, price: float, change_pct: float, market_trend: dict):
    try:
        OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY", "")
        if not OPENROUTER_KEY:
            print("[AI ERROR] Thiếu OPENROUTER_API_KEY")
            return None

        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {OPENROUTER_KEY}", "Content-Type": "application/json"}
            payload = {
                "model": os.getenv("OPENROUTER_MODEL", "deepseek-chat-v3-0324:free"),
                "messages": [
                    {"role": "system", "content": "Bạn là chuyên gia phân tích crypto. Luôn trả JSON dạng {\"side\":\"LONG/SHORT\",\"strength\":%,\"reason\":\"...\"}"},
                    {"role": "user", "content": f"Phân tích coin {symbol}, giá={price}, biến động 24h={change_pct}%, xu hướng thị trường={market_trend}"}
                ]
            }
            async with session.post(
                os.getenv("OPENROUTER_API_URL", "https://openrouter.ai/api/v1/chat/completions"),
                headers=headers, data=json.dumps(payload), timeout=40
            ) as resp:
                data = await resp.json()
                if "choices" not in data:
                    print("[AI ERROR RESPONSE]", data)
                    return None

                ai_text = data["choices"][0]["message"]["content"]

                # Bắt buộc parse JSON
                try:
                    result = json.loads(ai_text)
                except:
                    print("[AI JSON ERROR]", ai_text)
                    return None

                strength = max(50, min(100, result.get("strength", 70)))
                return {
                    "side": result.get("side", "LONG"),
                    "strength": strength,
                    "reason": result.get("reason", "AI phân tích")
                }
    except Exception as e:
        print(f"[ERROR] analyze_coin({symbol}): {e}")
        return None
