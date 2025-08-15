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
    Lấy coin futures biến động mạnh nhất.
    Đảm bảo luôn có change_pct chính xác.
    """
    tickers = await get_all_tickers()
    futures = [t for t in tickers if t.get("symbol", "").endswith("_USDT")]

    for f in futures:
        try:
            last_price = float(f.get("lastPrice", 0))
            rf = float(f.get("riseFallRate", 0))
            # Nếu |rf| < 1 => coi là tỉ lệ, chuyển sang %
            change_pct = rf * 100 if abs(rf) < 1 else rf
            f["change_pct"] = change_pct
            f["lastPrice"] = last_price
        except:
            f["change_pct"] = 0
            f["lastPrice"] = 0

    futures.sort(key=lambda x: abs(x["change_pct"]), reverse=True)
    return futures[:limit]
