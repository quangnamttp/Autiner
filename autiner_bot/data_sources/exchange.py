# autiner_bot/data_sources/exchange.py
import aiohttp
from autiner_bot.settings import S

async def get_usdt_vnd_rate():
    """Lấy tỷ giá USDT → VND từ MEXC."""
    async with aiohttp.ClientSession() as session:
        async with session.get(S.MEXC_TICKER_VNDC_URL) as resp:
            data = await resp.json()
            try:
                ticker = data.get("data", [])[0]
                return float(ticker["last"])
            except:
                return None
