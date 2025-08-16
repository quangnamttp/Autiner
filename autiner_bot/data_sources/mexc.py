import aiohttp
import numpy as np
from autiner_bot.settings import S

# =============================
# Fetch helpers
# =============================
async def fetch_json(url: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            return await resp.json()

async def get_all_tickers():
    try:
        data = await fetch_json(S.MEXC_TICKER_URL)
        return data.get("data", [])
    except Exception as e:
        print(f"[ERROR] get_all_tickers: {e}")
        return []

async def get_klines(symbol: str, limit: int = 100):
    try:
        url = f"https://contract.mexc.com/api/v1/contract/kline/{symbol}?interval=Min15&limit={limit}"
        data = await fetch_json(url)
        return data.get("data", [])[::-1]
    except Exception as e:
        print(f"[ERROR] get_klines({symbol}): {e}")
        return []

# =============================
# Indicators
# =============================
def calc_rsi(prices, period: int = 14):
    if len(prices) < period + 1:
        return None
    deltas = np.diff(prices)
    seed = deltas[:period]
    up = seed[seed >= 0].sum() / period
    down = -seed[seed < 0].sum() / period
    rs = up / down if down != 0 else 0
    rsi = np.zeros_like(prices)
    rsi[:period] = 50
    for i in range(period, len(prices)):
        delta = deltas[i - 1]
        upval = max(delta, 0)
        downval = -min(delta, 0)
        up = (up * (period - 1) + upval) / period
        down = (down * (period - 1) + downval) / period
        rs = up / down if down != 0 else 0
        rsi[i] = 100 - 100 / (1 + rs)
    return rsi[-1]

def calc_ema(prices, period: int = 20):
    if len(prices) < period:
        return None
    weights = np.exp(np.linspace(-1., 0., period))
    weights /= weights.sum()
    a = np.convolve(prices, weights, mode='full')[:len(prices)]
    return a[-1]

def calc_macd(prices):
    if len(prices) < 26:
        return None, None
    ema12 = calc_ema(prices, 12)
    ema26 = calc_ema(prices, 26)
    if ema12 is None or ema26 is None:
        return None, None
    macd = ema12 - ema26
    signal = calc_ema(prices, 9)
    return macd, signal

def calc_bollinger(prices, period: int = 20, num_std: int = 2):
    if len(prices) < period:
        return None, None
    sma = np.mean(prices[-period:])
    std = np.std(prices[-period:])
    upper = sma + num_std * std
    lower = sma - num_std * std
    return upper, lower

# =============================
# Analyzer
# =============================
async def analyze_coin(symbol: str):
    klines = await get_klines(symbol, limit=100)
    if not klines:
        return None

    closes = np.array([float(k[4]) for k in klines])
    volumes = np.array([float(k[5]) for k in klines])
    last_price = closes[-1]

    # Indicators
    rsi = calc_rsi(closes)
    ema20 = calc_ema(closes, 20)
    macd, macd_signal = calc_macd(closes)
    bb_upper, bb_lower = calc_bollinger(closes)

    score = 0
    reason = []

    if rsi:
        if rsi < 30: score += 2; reason.append("RSI quá bán")
        elif rsi > 70: score -= 2; reason.append("RSI quá mua")

    if ema20:
        if last_price > ema20: score += 1; reason.append("Giá trên EMA20")
        else: score -= 1; reason.append("Giá dưới EMA20")

    if macd and macd_signal:
        if macd > macd_signal: score += 1; reason.append("MACD bullish")
        else: score -= 1; reason.append("MACD bearish")

    if bb_upper and bb_lower:
        if last_price > bb_upper: score -= 1; reason.append("Trên BB trên")
        elif last_price < bb_lower: score += 1; reason.append("Dưới BB dưới")

    avg_vol = np.mean(volumes[-20:])
    if volumes[-1] > avg_vol * 1.5:
        score += 1; reason.append("Volume tăng mạnh")

    return {
        "symbol": symbol,
        "lastPrice": last_price,
        "score": score,
        "reasons": reason,
    }

# =============================
# Top signals
# =============================
async def get_top_signals(limit=5):
    tickers = await get_all_tickers()
    futures = [t for t in tickers if t.get("symbol", "").endswith("_USDT")]

    results = []
    for f in futures:
        analyzed = await analyze_coin(f["symbol"])
        if analyzed:
            results.append(analyzed)

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:limit]
