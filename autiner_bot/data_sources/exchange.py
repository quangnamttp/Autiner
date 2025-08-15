import aiohttp
import asyncio
from autiner_bot.settings import S

async def get_usdt_vnd_rate(retry: int = 2):
    """
    Lấy tỷ giá USDT/VND từ MEXC.
    Có retry khi lỗi để tránh bị None.
    """
    for _ in range(retry):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(S.MEXC_TICKER_VNDC_URL) as resp:
                    data = await resp.json()
                    ticker = data.get("data", [])[0]
                    rate = float(ticker["last"])
                    if rate > 0:
                        return rate
        except:
            await asyncio.sleep(0.5)
    return None
