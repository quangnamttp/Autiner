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


async def detect_trend(limit: int = 5):
    """
    Lọc coin theo trend mạnh:
    - Lấy dữ liệu từ MEXC ticker.
    - Lọc coin có volume cao (bỏ coin rác).
    - Nhận diện trend dựa vào symbol.
    - Tính RSI & MA để sàng lọc thêm.
    - Ưu tiên coin biến động mạnh nhất.
    Trả về: danh sách coin kèm trend & phân tích cơ bản.
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
                    if volume < 1_000_000:  # loại coin thanh khoản thấp
                        continue

                    change_pct = float(c.get("riseFallRate", 0))
                    last_price = float(c.get("lastPrice", 0))

                    # Nhận diện trend
                    trend = "Khác"
                    for t, kws in TREND_KEYWORDS.items():
                        if any(kw in c["symbol"].upper() for kw in kws):
                            trend = t
                            break

                    # Lấy dữ liệu kỹ thuật
                    closes = await fetch_klines(c["symbol"], limit=30)
                    if not closes:
                        closes = [last_price] * 20

                    rsi = calculate_rsi(closes, 14)
                    ma5 = np.mean(closes[-5:]) if len(closes) >= 5 else last_price
                    ma20 = np.mean(closes[-20:]) if len(closes) >= 20 else last_price

                    results.append({
                        "symbol": c["symbol"],
                        "lastPrice": last_price,
                        "volume": volume,
                        "change_pct": change_pct,
                        "trend": trend,
                        "rsi": rsi,
                        "ma5": ma5,
                        "ma20": ma20
                    })

                # Sắp xếp theo độ biến động mạnh nhất
                sorted_coins = sorted(results, key=lambda x: abs(x["change_pct"]), reverse=True)
                return sorted_coins[:limit]

    except Exception as e:
        print(f"[ERROR] detect_trend: {e}")
        return []
