import aiohttp
import numpy as np
import traceback
import random

MEXC_BASE_URL = "https://contract.mexc.com"

# =============================
# Lấy dữ liệu ticker Futures (top coin)
# =============================
async def get_top_futures(limit: int = 30):
    try:
        url = f"{MEXC_BASE_URL}/api/v1/contract/ticker"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                data = await resp.json()
                if not data or "data" not in data:
                    return []
                tickers = data["data"]

                coins = []
                for t in tickers:
                    if not t.get("symbol", "").endswith("_USDT"):
                        continue
                    last_price = float(t["lastPrice"])
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
# Lấy tỷ giá USDT/VND từ Binance P2P
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
            async with session.post(url, json=payload, timeout=10) as resp:
                if resp.status != 200:
                    print(f"[ERROR] get_usdt_vnd_rate: HTTP {resp.status}")
                    return 0
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
# Market sentiment (long/short %)
# =============================
async def get_market_sentiment():
    try:
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
    except Exception:
        return {"long": 50, "short": 50}


# =============================
# Phân tích xu hướng thị trường (cho Daily)
# =============================
async def analyze_market_trend(limit: int = 20):
    """
    Dùng cho daily_reports để hiển thị:
    - % Long / Short
    - Xu hướng (TĂNG / GIẢM / Sideway)
    - Top coin nổi bật
    """
    try:
        coins = await get_top_futures(limit=limit)
        if not coins:
            return {
                "long": 50.0,
                "short": 50.0,
                "trend": "❓ Không xác định",
                "top": []
            }

        ups = [c for c in coins if c["change_pct"] > 0]
        downs = [c for c in coins if c["change_pct"] < 0]

        total = len(ups) + len(downs)
        if total == 0:
            long_pct, short_pct = 50.0, 50.0
        else:
            long_pct = round(len(ups) / total * 100, 1)
            short_pct = round(len(downs) / total * 100, 1)

        # Xác định xu hướng
        if long_pct > short_pct + 5:  # lệch 5% trở lên coi là có trend
            trend = "📈 Xu hướng TĂNG (phe LONG chiếm ưu thế)"
        elif short_pct > long_pct + 5:
            trend = "📉 Xu hướng GIẢM (phe SHORT chiếm ưu thế)"
        else:
            trend = "⚖️ Thị trường sideway"

        # Lấy top coin biến động mạnh
        top = sorted(coins, key=lambda x: abs(x.get("change_pct", 0)), reverse=True)[:5]

        return {
            "long": long_pct,
            "short": short_pct,
            "trend": trend,
            "top": top
        }
    except Exception as e:
        print(f"[ERROR] analyze_market_trend: {e}")
        print(traceback.format_exc())
        return {
            "long": 50.0,
            "short": 50.0,
            "trend": "❓ Không xác định",
            "top": []
        }


# =============================
# Lấy dữ liệu nến (Kline) cho 1 coin
# =============================
async def get_kline(symbol: str, interval: str = "Min1", limit: int = 100):
    """
    Lấy dữ liệu nến cho coin.
    :param symbol: Ví dụ "BTC_USDT"
    :param interval: Min1, Min5, Min15, Min30, Hour1, Day1
    :param limit: số lượng nến (tối đa 1000)
    :return: list OHLCV [timestamp, open, high, low, close, volume]
    """
    try:
        url = f"{MEXC_BASE_URL}/api/v1/contract/kline/{symbol}?interval={interval}&limit={limit}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                data = await resp.json()
                if not data or "data" not in data:
                    return []
                return data["data"]  # mỗi item: [timestamp, open, high, low, close, volume]
    except Exception as e:
        print(f"[ERROR] get_kline({symbol}): {e}")
        print(traceback.format_exc())
        return []
