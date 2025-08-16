import aiohttp

COINGECKO_API = "https://api.coingecko.com/api/v3/coins/{}"

async def get_coin_trend(coin_id: str):
    """
    Nhận diện trend / category của coin từ Coingecko.
    coin_id: ví dụ 'bitcoin', 'ethereum', 'arbitrum'...
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(COINGECKO_API.format(coin_id), timeout=10) as resp:
                data = await resp.json()
                if "categories" in data:
                    return data["categories"]  # list trend, ví dụ ["AI", "Layer 2"]
    except Exception as e:
        print(f"[ERROR] get_coin_trend {coin_id}: {e}")
    return []
