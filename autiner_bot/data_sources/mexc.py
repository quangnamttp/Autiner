import aiohttp
from autiner_bot.settings import S

# =============================
# Fetch JSON từ API
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
# Tính RSI (Relative Strength Index)
# =============================
def calculate_rsi(closes, period=14):
    if len(closes) < period + 1:
        return None

    gains, losses = [], []
    for i in range(1, period + 1):
        change = closes[-i] - closes[-i - 1]
        if change > 0:
            gains.append(change)
        else:
            losses.append(abs(change))

    avg_gain = sum(gains) / period if gains else 0
    avg_loss = sum(losses) / period if losses else 1e-9  # tránh chia 0

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

# =============================
# Tính MA (Moving Average)
# =============================
def calculate_ma(closes, period=20):
    if len(closes) < period:
        return None
    return sum(closes[-period:]) / period

# =============================
# Lấy top coin biến động + phân tích
# =============================
async def get_top_moving_coins(limit=5):
    tickers = await get_all_tickers()
    futures = [t for t in tickers if t.get("symbol", "").endswith("_USDT")]

    # Chuẩn hóa dữ liệu
    for f in futures:
        try:
            last_price = float(f.get("lastPrice", 0))
            rf = float(f.get("riseFallRate", 0))
            change_pct = rf * 100 if abs(rf) < 10 else rf

            f["lastPrice"] = last_price
            f["change_pct"] = change_pct
            f["volume"] = float(f.get("volume", 0))
        except:
            f["lastPrice"] = 0.0
            f["change_pct"] = 0.0
            f["volume"] = 0.0

    # Lọc theo volume cao nhất + biến động mạnh
    futures.sort(key=lambda x: (x["volume"], abs(x["change_pct"])), reverse=True)
    top = futures[:limit]

    # Gắn thêm phân tích RSI + MA
    results = []
    for coin in top:
        try:
            kl_url = S.MEXC_KLINES_URL.format(sym=coin["symbol"])
            kl_data = await fetch_json(kl_url)

            closes = [float(c[4]) for c in kl_data.get("data", [])]  # close price
            rsi = calculate_rsi(closes)
            ma = calculate_ma(closes)

            coin["rsi"] = round(rsi, 2) if rsi else None
            coin["ma"] = round(ma, 4) if ma else None
        except Exception as e:
            print(f"[WARN] RSI/MA error {coin['symbol']}: {e}")
            coin["rsi"] = None
            coin["ma"] = None

        results.append(coin)

    return results
