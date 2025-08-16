# autiner_bot/strategies/trend_detector.py
import aiohttp
import numpy as np
from autiner_bot.settings import S
from autiner_bot.strategies.signal_analyzer import calculate_rsi, fetch_klines

# =============================
# Các trend chính
# =============================
TREND_KEYWORDS = {
    "AI": ["AI", "GPT", "NEURAL", "BOT", "FET", "RNDR", "AGIX"],
    "Layer2": ["ARB", "ARBITRUM", "OP", "OPTIMISM", "ZKSYNC", "STARK", "SUI", "MATIC"],
    "DeFi": ["DEX", "UNI", "CAKE", "LENDING", "AAVE", "YFI", "CRV", "COMP"],
    "GameFi": ["GAME", "ARENA", "PLAY", "METAVERSE", "SAND", "MANA", "GALA", "AXS"],
    "Meme": ["INU", "DOGE", "SHIB", "PEPE", "FLOKI", "MEME", "BONK"]
}


# =============================
# Hàm lọc coin theo trend & volume
# =============================
async def detect_trend(limit: int = 5):
    """
    Lọc coin theo trend mạnh:
    1. Lấy dữ liệu MEXC ticker.
    2. Lọc coin có volume cao nhất (top 50) để tránh coin rác.
    3. Nhận diện trend dựa vào symbol.
    4. Tính RSI & MA để phân tích.
    5. Chọn ra N coin biến động mạnh nhất.
    """
    try:
        url = S.MEXC_TICKER_URL
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                data = await resp.json()
                if not data.get("success"):
                    return []

                # =============================
                # B1. Gom toàn bộ coin USDT
                # =============================
                candidates = []
                for c in data.get("data", []):
                    if not c["symbol"].endswith("_USDT"):
                        continue
                    volume = float(c.get("volume", 0))
                    if volume <= 0:
                        continue
                    candidates.append({
                        "symbol": c["symbol"],
                        "lastPrice": float(c.get("lastPrice", 0)),
                        "volume": volume,
                        "change_pct": float(c.get("riseFallRate", 0)),
                    })

                if not candidates:
                    return []

                # =============================
                # B2. Giữ lại top 50 coin volume cao nhất
                # =============================
                top_volume = sorted(candidates, key=lambda x: x["volume"], reverse=True)[:50]

                results = []
                for coin in top_volume:
                    last_price = coin["lastPrice"]

                    # Nhận diện trend
                    trend = "Khác"
                    for t, kws in TREND_KEYWORDS.items():
                        if any(kw in coin["symbol"].upper() for kw in kws):
                            trend = t
                            break

                    # Lấy dữ liệu kỹ thuật (RSI & MA)
                    closes = await fetch_klines(coin["symbol"], limit=30)
                    if not closes:
                        closes = [last_price] * 20

                    rsi = calculate_rsi(closes, 14)
                    ma5 = np.mean(closes[-5:]) if len(closes) >= 5 else last_price
                    ma20 = np.mean(closes[-20:]) if len(closes) >= 20 else last_price

                    results.append({
                        **coin,
                        "trend": trend,
                        "rsi": rsi,
                        "ma5": ma5,
                        "ma20": ma20
                    })

                # =============================
                # B3. Chọn 5 coin biến động % mạnh nhất
                # =============================
                sorted_coins = sorted(results, key=lambda x: abs(x["change_pct"]), reverse=True)
                return sorted_coins[:limit]

    except Exception as e:
        print(f"[ERROR] detect_trend: {e}")
        return []
