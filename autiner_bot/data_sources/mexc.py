import aiohttp
from autiner_bot.settings import S

async def fetch_json(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            return await resp.json()

async def get_all_tickers():
    """Lấy tất cả tickers futures từ MEXC."""
    data = await fetch_json(S.MEXC_TICKER_URL)
    return data.get("data", [])

async def get_top_moving_coins(limit=5):
    """
    Lấy coin futures có biến động mạnh nhất hiện tại (không giới hạn turnover).
    - limit: số lượng coin trả về.
    """
    tickers = await get_all_tickers()
    futures = [t for t in tickers if t.get("symbol", "").endswith("_USDT")]

    for f in futures:
        try:
            last_price = float(f["lastPrice"])
            high = float(f.get("highPrice", last_price))
            low = float(f.get("lowPrice", last_price))
            if low > 0:
                change_pct = ((high - low) / low) * 100
            else:
                change_pct = 0
            f["change_pct"] = change_pct
            f["lastPrice"] = last_price
        except:
            f["change_pct"] = 0
            f["lastPrice"] = 0

    futures.sort(key=lambda x: abs(x["change_pct"]), reverse=True)
    return futures[:limit]
