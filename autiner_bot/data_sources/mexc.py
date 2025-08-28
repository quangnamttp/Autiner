import aiohttp, os, json, traceback

MEXC_BASE_URL = "https://contract.mexc.com"

# =============================
# Lấy danh sách coin Futures
# =============================
async def get_top_futures(limit: int = 200):
    try:
        url = f"{MEXC_BASE_URL}/api/v1/contract/ticker"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=15) as resp:
                data = await resp.json()
                tickers = data.get("data", [])
                coins = []
                for t in tickers:
                    sym = t.get("symbol", "")
                    if not sym.endswith("_USDT"):
                        continue
                    last_price = float(t.get("lastPrice", 0))
                    if last_price < 0.0001:
                        continue
                    coins.append({
                        "symbol": sym,
                        "lastPrice": last_price,
                        "volume": float(t.get("amount24", 0)),
                        "change_pct": float(t.get("riseFallRate", 0)) * 100
                    })
                return coins[:limit]
    except Exception as e:
        print("[ERROR] get_top_futures:", e)
        print(traceback.format_exc())
        return []

# =============================
# Lấy tỷ giá USDT/VND (Binance P2P)
# =============================
async def get_usdt_vnd_rate() -> float:
    url = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"
    payload = {"asset":"USDT","fiat":"VND","merchantCheck":False,"page":1,"rows":10,"tradeType":"SELL"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=15) as resp:
                data = await resp.json()
                advs = data.get("data", [])
                prices = [float(ad["adv"]["price"]) for ad in advs[:5] if "adv" in ad]
                return sum(prices) / len(prices) if prices else 0
    except Exception as e:
        print("[ERROR] get_usdt_vnd_rate:", e)
        return 0

# =============================
# AI phân tích coin (chỉ thủ công)
# =============================
async def analyze_coin(symbol: str, price: float, change_pct: float, market_trend: dict):
    try:
        key = os.getenv("OPENROUTER_API_KEY", "")
        if not key:
            return None
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
            payload = {
                "model": os.getenv("OPENROUTER_MODEL", "deepseek-chat-v3-0324:free"),
                "messages": [
                    {"role":"system","content":"Bạn là bot giao dịch crypto. Trả lời JSON: {\"side\":\"LONG/SHORT\",\"strength\":%,\"reason\":\"...\"}"},
                    {"role":"user","content":f"Phân tích coin {symbol}, giá={price}, biến động={change_pct}%, xu hướng={market_trend}"}
                ]
            }
            async with session.post(
                os.getenv("OPENROUTER_API_URL","https://openrouter.ai/api/v1/chat/completions"),
                headers=headers, data=json.dumps(payload), timeout=30
            ) as resp:
                data = await resp.json()
                if "choices" not in data:
                    print("[AI ERROR]", data)
                    return None
                ai_text = data["choices"][0]["message"]["content"]
                result = json.loads(ai_text)  # bắt buộc JSON
                strength = max(50, min(100, result.get("strength", 70)))
                return {
                    "side": result.get("side","LONG"),
                    "strength": strength,
                    "reason": result.get("reason","AI phân tích")
                }
    except Exception as e:
        print(f"[ERROR] analyze_coin({symbol}): {e}")
        return None
