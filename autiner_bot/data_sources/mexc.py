import aiohttp
import numpy as np
import traceback

MEXC_BASE_URL = "https://contract.mexc.com"

# =============================
# Lấy top futures theo volume
# =============================
async def get_top_futures(limit: int = 15):
    try:
        url = f"{MEXC_BASE_URL}/api/v1/contract/ticker"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                data = await resp.json()
                if not data or "data" not in data:
                    raise Exception("[MEXC] Không có dữ liệu trả về")
                tickers = data["data"]

                coins = []
                for t in tickers:
                    if not t.get("symbol", "").endswith("_USDT"):
                        continue
                    last_price = float(t["lastPrice"])
                    if last_price < 0.01:   # bỏ coin rác
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
# Lấy tỷ giá USDT/VND từ Binance P2P (realtime, không fallback)
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
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, timeout=10) as resp:
            if resp.status != 200:
                raise Exception(f"[Binance P2P] HTTP {resp.status}")
            data = await resp.json()
            advs = data.get("data", [])
            if not advs:
                raise Exception("[Binance P2P] Không có dữ liệu trả về")
            prices = [float(ad["adv"]["price"]) for ad in advs[:5] if "adv" in ad]
            if not prices:
                raise Exception("[Binance P2P] Không lấy được giá USDT/VND")
            return sum(prices) / len(prices)


# =============================
# Lấy sentiment thị trường
# =============================
async def get_market_sentiment():
    coins = await get_top_futures(limit=30)
    if not coins:
        return {"long": 50, "short": 50}
    ups = sum(1 for c in coins if c["change_pct"] >= 0)
    downs = len(coins) - ups
    total = max(1, ups + downs)
    return {
        "long": round(ups / total * 100, 2),
        "short": round(downs / total * 100, 2)
    }
