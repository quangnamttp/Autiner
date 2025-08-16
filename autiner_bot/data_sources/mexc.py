import aiohttp
import numpy as np
import talib
from autiner_bot.settings import S

# =============================
# Hàm fetch
# =============================
async def fetch_json(url: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=10) as resp:
            return await resp.json()

# =============================
# Lấy toàn bộ tickers
# =============================
async def get_all_tickers():
    """Lấy tất cả tickers futures từ MEXC."""
    try:
        data = await fetch_json(S.MEXC_TICKER_URL)
        return data.get("data", [])
    except Exception as e:
        print(f"[ERROR] get_all_tickers: {e}")
        return []

# =============================
# Lấy dữ liệu Kline
# =============================
async def get_klines(symbol: str, limit: int = 200):
    """Lấy dữ liệu nến để phân tích kỹ thuật."""
    try:
        url = S.MEXC_KLINES_URL.format(sym=symbol)
        data = await fetch_json(url)
        klines = data.get("data", [])
        closes = [float(k[4]) for k in klines[-limit:]]  # giá đóng cửa
        return np.array(closes, dtype=float)
    except Exception as e:
        print(f"[ERROR] get_klines {symbol}: {e}")
        return np.array([])

# =============================
# Phân tích kỹ thuật
# =============================
def analyze_coin(closes: np.ndarray):
    """Phân tích kỹ thuật chuyên sâu (RSI, MA, MACD)."""
    if closes.size < 50:
        return {"score": 0, "signals": []}

    signals = []
    score = 0

    # RSI
    rsi = talib.RSI(closes, timeperiod=14)
    latest_rsi = rsi[-1]
    if latest_rsi < 30:
        signals.append("RSI quá bán → LONG")
        score += 2
    elif latest_rsi > 70:
        signals.append("RSI quá mua → SHORT")
        score += 2

    # MA crossover
    ma_fast = talib.SMA(closes, timeperiod=9)
    ma_slow = talib.SMA(closes, timeperiod=21)
    if ma_fast[-1] > ma_slow[-1]:
        signals.append("MA9 > MA21 → xu hướng tăng")
        score += 2
    else:
        signals.append("MA9 < MA21 → xu hướng giảm")
        score += 2

    # MACD
    macd, signal, hist = talib.MACD(closes, 12, 26, 9)
    if hist[-1] > 0:
        signals.append("MACD dương → xu hướng tăng")
        score += 1
    else:
        signals.append("MACD âm → xu hướng giảm")
        score += 1

    return {"score": score, "signals": signals}

# =============================
# Chọn top coin mạnh nhất
# =============================
async def get_top_moving_coins(limit=5):
    tickers = await get_all_tickers()
    futures = [t for t in tickers if t.get("symbol", "").endswith("_USDT")]

    results = []
    for f in futures:
        try:
            symbol = f["symbol"]
            last_price = float(f.get("lastPrice", 0))
            volume = float(f.get("volume", 0))
            rf = float(f.get("riseFallRate", 0))
            change_pct = rf * 100 if abs(rf) < 10 else rf

            closes = await get_klines(symbol)
            analysis = analyze_coin(closes)

            score = analysis["score"]
            # Ưu tiên volume + biến động + phân tích kỹ thuật
            final_score = score + (abs(change_pct) / 2) + (np.log(volume + 1) / 10)

            results.append({
                "symbol": symbol,
                "lastPrice": last_price,
                "volume": volume,
                "change_pct": change_pct,
                "score": final_score,
                "signals": analysis["signals"]
            })
        except Exception:
            continue

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:limit]
