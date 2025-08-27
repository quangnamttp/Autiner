import aiohttp
import traceback
import os
import json

MEXC_BASE_URL = "https://contract.mexc.com"

# =============================
# Lấy danh sách coin Futures (lọc giá > 0.01)
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
                    coins.append({
                        "symbol": t["symbol"],
                        "lastPrice": last_price,
                        "volume": float(t.get("amount24", 0)),
                        "change_pct": float(t.get("riseFallRate", 0)) * 100
                    })

                coins.sort(key=lambda x: x["volume"], reverse=True)
                return coins[:limit]
    except Exception as e:
        print(f"[ERROR] get_top_futures: {e}")
        print(traceback.format_exc())
        return []


# =============================
# Lấy tỷ giá USDT/VND (Binance P2P)
# =============================
async def get_usdt_vnd_rate() -> float:
    url = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"
    payload = {
        "asset": "USDT",
        "fiat": "VND",
        "merchantCheck": False,
        "page": 1,
        "rows": 10,
        "tradeType": "SELL"
    }
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
# Phân tích 1 coin (BẮT BUỘC AI)
# =============================
async def analyze_single_coin(symbol: str):
    try:
        OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY", "")
        if not OPENROUTER_KEY:
            print("[AI ERROR] Chưa có OPENROUTER_API_KEY")
            return None

        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {OPENROUTER_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-r1"),
                "messages": [
                    {"role": "system", "content": "Bạn là chuyên gia phân tích crypto. Trả lời JSON với: side (LONG/SHORT), strength (%), reason."},
                    {"role": "user", "content": f"Phân tích coin {symbol} trên MEXC Futures và đưa ra tín hiệu giao dịch."}
                ]
            }
            async with session.post("https://openrouter.ai/api/v1/chat/completions",
                                     headers=headers, data=json.dumps(payload), timeout=30) as resp:
                data = await resp.json()

                # 👇 In log chi tiết để debug
                print("=== AI RAW RESPONSE ===")
                print(json.dumps(data, indent=2, ensure_ascii=False))

                if "choices" not in data:
                    print("[AI ERROR] Không có 'choices'")
                    return None

                ai_text = data["choices"][0]["message"]["content"]

                try:
                    result = json.loads(ai_text)
                except:
                    side = "LONG" if "LONG" in ai_text.upper() else "SHORT"
                    return {"side": side, "strength": 75, "reason": ai_text}

                return {
                    "side": result.get("side", "LONG"),
                    "strength": result.get("strength", 75),
                    "reason": result.get("reason", ai_text)
                }

    except Exception as e:
        print(f"[ERROR] analyze_single_coin({symbol}): {e}")
        return None
