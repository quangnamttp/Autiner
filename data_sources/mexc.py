# autiner_bot/data_sources/mexc.py
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

async def get_top_coins_by_volume(limit=5):
    """Top coin có volume cao nhất."""
    tickers = await get_all_tickers()
    futures = [t for t in tickers if t.get("symbol", "").endswith("_USDT")]
    futures.sort(key=lambda x: float(x.get("turnover", 0)), reverse=True)
    return futures[:limit]

async def get_funding_rates():
    """Lấy funding rate cho tất cả coin."""
    data = await fetch_json(S.MEXC_FUNDING_URL)
    return data.get("data", [])
