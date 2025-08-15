import aiohttp
from autiner_bot.settings import S

async def fetch_json(url: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            return await resp.json()

async def get_usdt_vnd_rate():
    """Lấy tỷ giá USDT → VND từ MEXC."""
    try:
        data = await fetch_json(S.MEXC_TICKER_VNDC_URL)
        ticker_list = data.get("data", [])
        if ticker_list and isinstance(ticker_list, list):
            return float(ticker_list[0]["last"])
    except Exception as e:
        print(f"[ERROR] get_usdt_vnd_rate: {e}")
    return None
