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

async def get_top_moving_coins(limit=8, min_volume=1_000_000, min_change=1.0):
    """
    Lọc coin biến động mạnh nhất trong 1 giờ qua và có volume lớn.
    - limit: số coin trả về
    - min_volume: tối thiểu volume USDT
    - min_change: % biến động tối thiểu
    """
    tickers = await get_all_tickers()
    futures = [t for t in tickers if t.get("symbol", "").endswith("_USDT")]

    coins = []
    for t in futures:
        try:
            change_pct = abs(float(t.get("riseFallRate", 0))) * 100  # % biến động
            volume = float(t.get("turnover", 0))
            if volume >= min_volume and change_pct >= min_change:
                coins.append({
                    "symbol": t["symbol"],
                    "changePct": change_pct,
                    "volume": volume,
                    "lastPrice": float(t.get("lastPrice", 0))
                })
        except:
            continue

    coins.sort(key=lambda x: x["changePct"], reverse=True)
    return coins[:limit]
