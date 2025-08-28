import aiohttp
import traceback
import os
import json

MEXC_BASE_URL = "https://contract.mexc.com"

# =============================
# Lấy danh sách coin Futures (lọc giá > 0.01, chọn biến động mạnh nhất)
# =============================
async def get_top_futures(limit: int = 50):
    try:
        url = f"{MEXC_BASE_URL}/api/v1/contract/ticker"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=15) as resp:
                data = await resp.json()
                if not data or "data" not in data:
                    return []
                tickers = data["data"]

                coins = []
                for t in tickers:
                    if not t.get("symbol", "").endswith("_USDT"):
                        continue
                    last_price = float(t.get("lastPrice", 0))
                    if last_price < 0.01:  # bỏ coin rác
                        continue
                    change_pct = float(t.get("riseFallRate", 0)) * 100
                    coins.append({
                        "symbol": t["symbol"],
                        "lastPrice": last_price,
                        "volume": float(t.get("amount24", 0)),
                        "change_pct": change_pct,
                        "abs_change": abs(change_pct)
                    })

                # Ưu tiên biến động mạnh nhất trước, sau đó tới volume
                coins.sort(key=lambda x: (x["abs_change"], x["volume"]), reverse=True)
                return coins[:limit]
    except Exception as e:
        print(f"[ERROR] get_top_futures: {e}")
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
                if not advs:
                    return 0
                prices = [float(ad["adv"]["price"]) for ad in advs[:5] if "adv" in ad]
                return sum(prices) / len(prices) if prices else 0
    except Exception as e:
        print(f"[ERROR] get_usdt_vnd_rate: {e}")
        return 0


# =============================
# Market trend (daily summary)
# =============================
async def analyze_market_trend():
    try:
        coins = await get_top_futures(limit=50)
        if not coins:
            return {"trend": "❓ Không xác định", "long": 50, "short": 50}
        long_vol = sum(c["volume"] for c in coins if c["change_pct"] > 0)
        short_vol = sum(c["volume"] for c in coins if c["change_pct"] < 0)
        total = long_vol + short_vol
        if total == 0:
            return {"trend": "⚖️ Sideway", "long": 50, "short": 50}
        long_pct = round(long_vol / total * 100, 1)
        short_pct = round(short_vol / total * 100, 1)
        if long_pct > short_pct + 5:
            trend = "📈 Xu hướng TĂNG"
        elif short_pct > long_pct + 5:
            trend = "📉 Xu hướng GIẢM"
        else:
            trend = "⚖️ Sideway"
        return {"trend": trend, "long": long_pct, "short": short_pct}
    except Exception as e:
        print(f"[ERROR] analyze_market_trend: {e}")
        return {"trend": "❓ Không xác định", "long": 50, "short": 50}


# =============================
# AI phân tích coin (AUTO - JSON sạch, có retry)
# =============================
async def analyze_coin_auto(symbol: str, price: float, change_pct: float, market_trend: dict):
    OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY", "")
    if not OPENROUTER_KEY:
        print("[AI ERROR] Chưa có OPENROUTER_API_KEY")
        return None

    async def call_model(model_name: str, timeout: int = 45):
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {OPENROUTER_KEY}", "Content-Type": "application/json"}
            payload = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": "Bạn là bot giao dịch. Trả lời đúng JSON: {\"side\": \"LONG/SHORT\", \"strength\": %, \"reason\": \"...\"}"},
                    {"role": "user", "content": f"Phân tích {symbol}, giá={price}, biến động={change_pct}%, xu hướng={market_trend}"}
                ]
            }
            async with session.post(os.getenv("OPENROUTER_API_URL","https://openrouter.ai/api/v1/chat/completions"),
                                     headers=headers, data=json.dumps(payload), timeout=timeout) as resp:
                return await resp.json()

    try:
        # Model chính
        model_main = os.getenv("OPENROUTER_MODEL_AUTO", "meta-llama/llama-3.1-8b-instruct:free")
        data = await call_model(model_main)
        ai_text = data.get("choices", [{}])[0].get("message", {}).get("content", "")

        # ép parse JSON
        result = None
        try:
            result = json.loads(ai_text)
        except:
            try:
                start = ai_text.rfind("{")
                end = ai_text.rfind("}") + 1
                result = json.loads(ai_text[start:end])
            except:
                print(f"[AI AUTO ERROR] Parse JSON fail cho {symbol}, text={ai_text}")

        # nếu JSON lỗi, thử model phụ
        if not result:
            print(f"[AI AUTO] Thử lại với model phụ deepseek-chat-v3-0324:free cho {symbol}")
            data2 = await call_model("deepseek-chat-v3-0324:free")
            ai_text2 = data2.get("choices", [{}])[0].get("message", {}).get("content", "")
            try:
                result = json.loads(ai_text2)
            except:
                return None

        strength = max(50, min(100, result.get("strength", 70)))
        return {"side": result.get("side", "LONG"), "strength": strength, "reason": result.get("reason", "AI auto")}

    except Exception as e:
        print(f"[ERROR] analyze_coin_auto({symbol}): {e}")
        print(traceback.format_exc())
        return None


# =============================
# AI phân tích coin (MANUAL - có phân tích dài dòng)
# =============================
async def analyze_coin_manual(symbol: str):
    OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY", "")
    if not OPENROUTER_KEY:
        print("[AI ERROR] Chưa có OPENROUTER_API_KEY")
        return None

    try:
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {OPENROUTER_KEY}", "Content-Type": "application/json"}
            payload = {
                "model": os.getenv("OPENROUTER_MODEL_MANUAL", "deepseek-chat-v3-0324:free"),
                "messages": [
                    {"role": "system", "content": "Bạn là chuyên gia phân tích crypto. Phân tích chi tiết coin. Cuối cùng luôn trả JSON chuẩn: {\"side\": \"LONG/SHORT\", \"strength\": %, \"reason\": \"...\"}"},
                    {"role": "user", "content": f"Phân tích chi tiết coin {symbol} trên MEXC Futures"}
                ]
            }
            async with session.post(os.getenv("OPENROUTER_API_URL","https://openrouter.ai/api/v1/chat/completions"),
                                     headers=headers, data=json.dumps(payload), timeout=45) as resp:
                data = await resp.json()
                if "choices" not in data:
                    print("[AI MANUAL ERROR]", data)
                    return None
                ai_text = data["choices"][0]["message"]["content"]
                try:
                    start = ai_text.rfind("{")
                    end = ai_text.rfind("}") + 1
                    result = json.loads(ai_text[start:end])
                except:
                    side = "LONG" if "LONG" in ai_text.upper() else "SHORT"
                    result = {"side": side, "strength": 70, "reason": ai_text}
                strength = max(50, min(100, result.get("strength", 70)))
                return {"side": result.get("side", "LONG"), "strength": strength, "reason": result.get("reason", "AI manual")}
    except Exception as e:
        print(f"[ERROR] analyze_coin_manual({symbol}): {e}")
        return None
