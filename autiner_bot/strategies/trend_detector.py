# autiner_bot/strategies/trend_detector.py
import aiohttp
import numpy as np
from autiner_bot.settings import S
from autiner_bot.strategies.signal_analyzer import calculate_rsi, fetch_klines

TREND_KEYWORDS = {
    "AI": ["AI", "GPT", "NEURAL", "BOT", "FET", "RNDR", "AGIX"],
    "Layer2": ["ARB", "ARBITRUM", "OP", "OPTIMISM", "ZKSYNC", "STARK", "SUI", "MATIC"],
    "DeFi": ["DEX", "UNI", "CAKE", "LENDING", "AAVE", "YFI", "CRV", "COMP"],
    "GameFi": ["GAME", "ARENA", "PLAY", "METAVERSE", "SAND", "MANA", "GALA", "AXS"],
    "Meme": ["INU", "DOGE", "SHIB", "PEPE", "FLOKI", "MEME", "BONK"]
}


async def detect_trend(limit: int = 5, volume_top: int = 50):
    """
    Lọc coin theo trend mạnh:
    1. Lấy dữ liệu từ MEXC ticker.
    2. Lọc ra top {volume_top} coin có volume cao nhất.
    3. Trong đó, chọn {limit} coin có biến động mạnh nhất.
    4. Trả về: danh sách coin kèm trend & phân tích cơ bản.
    """
    try:
        url = S.MEXC_TICKER_URL
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                data = await resp.json()
                if not data.get("success"):
                    return []

                all_coins = []
                for c in data.get("data", []):
                    if not c["symbol"].endswith("_USDT"):
                        continue

                    volume = float(c.get("volume", 0))
                    last_price = float(c.get("lastPrice", 0))
                    change_pct = float(c.get("riseFallRate", 0))

                    # Nhận diện trend
                    trend = "Khác"
                    for t, kws in TREND_KEYWORDS.items():
                        if any(kw in c["symbol"].upper() for kw in kws):
                            trend = t
                            break

                    all_coins.append({
                        "symbol": c["symbol"],
                        "lastPrice": last_price,
                        "volume": volume,
                        "change_pct": change_pct,
                        "trend": trend
                    })

                # 1️⃣ Lọc top volume
                top_volume = sorted(all_coins, key=lambda x: x["volume"], reverse=True)[:volume_top]

                results = []
                for coin in top_volume:
                    closes = await fetch_klines(coin["symbol"], limit=30)
                    if not closes:
                        closes = [coin["lastPrice"]] * 20

                    rsi = calculate_rsi(closes, 14)
                    ma5 = np.mean(closes[-5:]) if len(closes) >= 5 else coin["lastPrice"]
                    ma20 = np.mean(closes[-20:]) if len(closes) >= 20 else coin["lastPrice"]

                    coin.update({
                        "rsi": rsi,
                        "ma5": ma5,
                        "ma20": ma20
                    })
                    results.append(coin)

                # 2️⃣ Chọn theo biến động mạnh nhất
                sorted_coins = sorted(results, key=lambda x: abs(x["change_pct"]), reverse=True)
                final_selection = sorted_coins[:limit]

                # In log (debug)
                print("[DEBUG] Top 50 theo volume:", [c["symbol"] for c in top_volume])
                print("[DEBUG] Chọn cuối cùng:", [c["symbol"] for c in final_selection])

                return final_selection

    except Exception as e:
        print(f"[ERROR] detect_trend: {e}")
        return []
