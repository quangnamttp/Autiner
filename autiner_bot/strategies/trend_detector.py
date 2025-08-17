# autiner_bot/strategies/trend_detector.py
import aiohttp
import numpy as np
from autiner_bot.settings import S
from autiner_bot.strategies.signal_analyzer import calculate_rsi, fetch_klines

# =============================
# Lọc top 20 coin volume cao nhất
# =============================
async def get_top20_futures(limit: int = 5):
    """
    Lấy dữ liệu từ MEXC Futures:
    1. Gọi API lấy toàn bộ ticker futures.
    2. Lọc top 20 coin có volume cao nhất tại thời điểm đó.
    3. Trong top 20 → chọn ra N coin biến động mạnh nhất.
    """
    try:
        url = S.MEXC_TICKER_URL
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=15) as resp:
                data = await resp.json()

                if "data" not in data:
                    print("[ERROR] API không trả về field 'data'")
                    return []

                # Lọc coin USDT
                candidates = []
                for c in data["data"]:
                    if not str(c.get("symbol", "")).endswith("_USDT"):
                        continue
                    volume = float(c.get("volume", 0) or 0)
                    price = float(c.get("lastPrice", 0) or 0)
                    change_pct = float(c.get("riseFallRate", 0) or 0)
                    if volume > 0 and price > 0:
                        candidates.append({
                            "symbol": c["symbol"],
                            "lastPrice": price,
                            "volume": volume,
                            "change_pct": change_pct,
                        })

                if not candidates:
                    print("[WARN] Không tìm thấy coin hợp lệ")
                    return []

                # Top 20 volume
                top20 = sorted(candidates, key=lambda x: x["volume"], reverse=True)[:20]

                results = []
                for coin in top20:
                    closes = await fetch_klines(coin["symbol"], limit=30)
                    if not closes:
                        closes = [coin["lastPrice"]] * 20

                    rsi = calculate_rsi(closes, 14)
                    ma5 = np.mean(closes[-5:]) if len(closes) >= 5 else coin["lastPrice"]
                    ma20 = np.mean(closes[-20:]) if len(closes) >= 20 else coin["lastPrice"]

                    results.append({
                        **coin,
                        "rsi": round(rsi, 2),
                        "ma5": round(ma5, 6),
                        "ma20": round(ma20, 6),
                    })

                # Chọn N coin biến động mạnh nhất
                sorted_coins = sorted(results, key=lambda x: abs(x["change_pct"]), reverse=True)
                return sorted_coins[:limit]

    except Exception as e:
        print(f"[ERROR] get_top20_futures: {e}")
        return []
