# autiner_bot/strategies/trend_detector.py
import aiohttp
from autiner_bot.settings import S

TREND_KEYWORDS = {
    "AI": ["AI", "GPT", "NEURAL", "BOT"],
    "Layer2": ["ARB", "ARBITRUM", "OP", "OPTIMISM", "ZKSYNC", "STARK", "SUI", "MATIC"],
    "DeFi": ["DEX", "UNI", "CAKE", "LENDING", "AAVE", "YFI"],
    "GameFi": ["GAME", "ARENA", "PLAY", "METAVERSE", "SAND", "MANA", "GALA"],
    "Meme": ["INU", "DOGE", "SHIB", "PEPE", "FLOKI", "MEME"]
}

async def detect_trend(limit: int = 5):
    """
    Lọc coin theo trend mạnh:
    - Lấy dữ liệu từ MEXC ticker.
    - Lọc coin có volume cao (bỏ coin rác).
    - Nhận diện trend dựa vào symbol.
    - Ưu tiên coin biến động mạnh nhất.
    Trả về: danh sách coin kèm trend.
    """
    try:
        url = S.MEXC_TICKER_URL
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                data = await resp.json()
                if not data.get("success"):
                    return []

                results = []
                for c in data.get("data", []):
                    if not c["symbol"].endswith("_USDT"):
                        continue
                    volume = float(c.get("volume", 0))
                    if volume < 1_000_000:
                        continue  # bỏ coin rác

                    change_pct = float(c.get("riseFallRate", 0))
                    trend = "Khác"
                    for t, kws in TREND_KEYWORDS.items():
                        if any(kw in c["symbol"].upper() for kw in kws):
                            trend = t
                            break

                    results.append({
                        "symbol": c["symbol"],
                        "lastPrice": float(c.get("lastPrice", 0)),
                        "volume": volume,
                        "change_pct": change_pct,
                        "trend": trend
                    })

                # Sort theo biến động mạnh nhất
                sorted_coins = sorted(results, key=lambda x: abs(x["change_pct"]), reverse=True)
                return sorted_coins[:limit]
    except Exception as e:
        print(f"[ERROR] detect_trend: {e}")
        return []
