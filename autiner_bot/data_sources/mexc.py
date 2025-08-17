import aiohttp
from autiner_bot.settings import S

# =============================
# Lấy tỷ giá USDT/VND (Binance P2P)
# =============================
async def get_usdt_vnd_rate():
    try:
        url = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"
        payload = {
            "asset": "USDT",
            "fiat": "VND",
            "tradeType": "BUY",
            "page": 1,
            "rows": 1,
            "payTypes": []
        }
        headers = {"Content-Type": "application/json"}

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers, timeout=10) as resp:
                data = await resp.json()
                if "data" in data and len(data["data"]) > 0:
                    return float(data["data"][0]["adv"]["price"])
    except Exception as e:
        print(f"[ERROR] get_usdt_vnd_rate: {e}")
    return 25000.0


# =============================
# Lấy top 20 coin Futures USDT theo volume
# =============================
async def get_top20_futures(limit: int = 20):
    try:
        url = "https://contract.mexc.com/api/v1/contract/tickers"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                data = await resp.json()
                if not data.get("success"):
                    return []

                coins = data.get("data", [])
                futures = []

                for c in coins:
                    if not c["symbol"].endswith("_USDT"):
                        continue

                    try:
                        futures.append({
                            "symbol": c["symbol"],
                            "lastPrice": float(c.get("lastPrice", 0)),
                            "volume": float(c.get("volume24", 0)),
                            "change_pct": float(c.get("riseFallRate", 0)) * 100,  # đổi về %
                        })
                    except:
                        continue

                # Sắp xếp theo volume giảm dần
                sorted_coins = sorted(futures, key=lambda x: x["volume"], reverse=True)

                return sorted_coins[:limit]

    except Exception as e:
        print(f"[ERROR] get_top20_futures: {e}")
    return []
