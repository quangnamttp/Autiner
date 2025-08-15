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
    Lấy coin futures có biến động mạnh nhất hiện tại.
    Đảm bảo lastPrice luôn là float và change_pct được tính đúng.
    """
    tickers = await get_all_tickers()
    futures = [t for t in tickers if t.get("symbol", "").endswith("_USDT")]

    for f in futures:
        try:
            f["lastPrice"] = float(f.get("lastPrice", 0))
        except:
            f["lastPrice"] = 0.0

        try:
            rf = float(f.get("riseFallRate", 0))
            if abs(rf) < 10:  # Trường hợp API trả về dạng 0.x
                f["change_pct"] = rf * 100
            else:
                f["change_pct"] = rf
        except:
            f["change_pct"] = 0.0

    futures.sort(key=lambda x: abs(x["change_pct"]), reverse=True)
    return futures[:limit]
