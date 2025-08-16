import aiohttp
import math
from autiner_bot.settings import S

# =============================
# Hàm fetch dữ liệu chung
# =============================
async def fetch_json(url: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=10) as resp:
            return await resp.json()

# =============================
# Lấy tất cả tickers futures
# =============================
async def get_all_tickers():
    try:
        data = await fetch_json(S.MEXC_TICKER_URL)
        return data.get("data", [])
    except Exception as e:
        print(f"[ERROR] get_all_tickers: {e}")
        return []

# =============================
# Phân tích kỹ thuật đơn giản (RSI, MA)
# =============================
async def get_technical_signal(symbol: str):
    try:
        url = S.MEXC_KLINES_URL.format(sym=symbol)
        data = await fetch_json(url)
        klines = data.get("data", [])
        if not klines or len(klines) < 14:
            return {"rsi": 50, "ma_signal": "NEUTRAL"}

        closes = [float(c[4]) for c in klines]  # c[4] = close
        # RSI đơn giản
        gains = []
        losses = []
        for i in range(1, 15):
            diff = closes[-i] - closes[-i - 1]
            if diff >= 0:
                gains.append(diff)
            else:
                losses.append(abs(diff))
        avg_gain = sum(gains) / max(1, len(gains))
        avg_loss = sum(losses) / max(1, len(losses))
        rsi = 100 - (100 / (1 + (avg_gain / max(1e-6, avg_loss))))

        # MA đơn giản
        ma_short = sum(closes[-7:]) / 7
        ma_long = sum(closes[-25:]) / 25
        ma_signal = "BULLISH" if ma_short > ma_long else "BEARISH"

        return {"rsi": round(rsi, 2), "ma_signal": ma_signal}
    except Exception as e:
        print(f"[ERROR] get_technical_signal {symbol}: {e}")
        return {"rsi": 50, "ma_signal": "NEUTRAL"}

# =============================
# Lấy top coin biến động + phân tích
# =============================
async def get_top_moving_coins(limit=5):
    tickers = await get_all_tickers()
    futures = [t for t in tickers if t.get("symbol", "").endswith("_USDT")]

    results = []
    for f in futures:
        try:
            symbol = f["symbol"]
            last_price = float(f.get("lastPrice", 0))
            rf = float(f.get("riseFallRate", 0))
            change_pct = rf * 100 if abs(rf) < 10 else rf

            tech = await get_technical_signal(symbol)

            results.append({
                "symbol": symbol,
                "lastPrice": last_price,
                "change_pct": change_pct,
                "rsi": tech["rsi"],
                "ma_signal": tech["ma_signal"],
                "score": abs(change_pct) + (100 - abs(50 - tech["rsi"])) / 2
            })
        except:
            continue

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:limit]

# =============================
# Giữ alias tương thích code cũ
# =============================
get_top_signals = get_top_moving_coins
