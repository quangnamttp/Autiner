import aiohttp
import time
from autiner_bot.settings import S

async def fetch_json(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            return await resp.json()

async def get_all_futures_tickers():
    """Lấy tất cả tickers Futures từ MEXC."""
    data = await fetch_json(S.MEXC_TICKER_URL)
    return data.get("data", [])

async def get_kline(symbol, limit=2):
    """
    Lấy dữ liệu nến 1 phút để tính biến động.
    limit=2 để lấy giá hiện tại và giá 1 phút trước.
    """
    url = S.MEXC_KLINES_URL.format(sym=symbol)
    data = await fetch_json(url)
    return data.get("data", [])

async def get_top_moving_coins(limit=5, min_turnover=500000):
    """
    Lọc các coin có biến động mạnh nhất dựa trên % thay đổi giá trong 15 phút gần nhất.
    Chỉ lấy coin có thanh khoản (turnover) >= min_turnover.
    """
    tickers = await get_all_futures_tickers()
    candidates = []

    for t in tickers:
        if not t.get("symbol", "").endswith("_USDT"):
            continue
        turnover = float(t.get("turnover", 0))
        if turnover < min_turnover:
            continue

        klines = await get_kline(t["symbol"], limit=16)
        if len(klines) < 2:
            continue

        try:
            price_now = float(klines[-1][4])  # close
            price_before = float(klines[0][4])
            change_pct = ((price_now - price_before) / price_before) * 100
            candidates.append({
                "symbol": t["symbol"],
                "lastPrice": price_now,
                "turnover": turnover,
                "change_pct": change_pct
            })
        except:
            continue

    # Sắp xếp theo biến động tuyệt đối giảm dần
    candidates.sort(key=lambda x: abs(x["change_pct"]), reverse=True)
    return candidates[:limit]
