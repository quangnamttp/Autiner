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
    2. Lọc coin USDT + volume cao.
    3. Nhận diện trend dựa vào symbol.
    4. Tính RSI & MA để phân tích.
    5. Chọn ra N coin biến động mạnh nhất.
    """
    try:
        url = S.MEXC_TICKER_URL
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=15) as resp:
                data = await resp.json()

                if "data" not in data:
                    print("[ERROR] detect_trend - API không trả về field 'data'")
                    return []

                candidates = []
                for c in data["data"]:
                    symbol = c.get("symbol", "")
                    if not symbol.endswith("_USDT"):
                        continue

                    # Dùng turnover (khối lượng quote) thay cho volume
                    volume = float(c.get("turnover", 0) or 0)

                    # Nếu API không có riseFallRate, ta tự tính %
                    last_price = float(c.get("lastPrice", 0) or 0)
                    open_price = float(c.get("openPrice", last_price) or last_price)
                    change_pct = ((last_price - open_price) / open_price * 100) if open_price > 0 else 0

                    if volume <= 0 or last_price <= 0:
                        continue

                    candidates.append({
                        "symbol": symbol,
                        "lastPrice": last_price,
                        "volume": volume,
                        "change_pct": change_pct,
                    })

                if not candidates:
                    print("[WARN] Không có coin USDT nào hợp lệ")
                    return []

                # =============================
                # B2. Giữ lại top 100 coin volume cao nhất
                # =============================
                top_volume = sorted(candidates, key=lambda x: x["volume"], reverse=True)[:100]

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
                        closes = [last_price] * 20  # fallback an toàn

                    try:
                        rsi = calculate_rsi(closes, 14)
                    except Exception:
                        rsi = 50.0

                    ma5 = np.mean(closes[-5:]) if len(closes) >= 5 else last_price
                    ma20 = np.mean(closes[-20:]) if len(closes) >= 20 else last_price

                    trade_style = "SCALPING" if abs(rsi - 50) > 20 else "SWING"

                    results.append({
                        **coin,
                        "trend": trend,
                        "rsi": round(rsi, 2),
                        "ma5": round(ma5, 6),
                        "ma20": round(ma20, 6),
                        "trade_style": trade_style
                    })

                # =============================
                # B3. Chọn N coin biến động mạnh nhất
                # =============================
                sorted_coins = sorted(results, key=lambda x: abs(x["change_pct"]), reverse=True)

                return sorted_coins[:limit]

    except Exception as e:
        print(f"[ERROR] detect_trend: {e}")
        return []
