import aiohttp
from autiner_bot.settings import S

# =============================
# Lấy danh sách coin USDT pair + volume
# =============================
async def get_usdt_pairs(min_volume: float = 5_000_000):
    """
    Trả về danh sách coin USDT có volume >= min_volume (lọc coin rác).
    """
    try:
        url = S.MEXC_TICKER_URL
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                data = await resp.json()
                if data.get("success") and "data" in data:
                    coins = [
                        {
                            "symbol": c["symbol"].replace("_USDT", ""),
                            "pair": c["symbol"],
                            "lastPrice": float(c.get("lastPrice", 0)),
                            "change_pct": float(c.get("riseFallRate", 0)),
                            "volume": float(c.get("volume", 0))
                        }
                        for c in data["data"]
                        if c["symbol"].endswith("_USDT")
                        and float(c.get("volume", 0)) >= min_volume
                    ]
                    return coins
    except Exception as e:
        print(f"[ERROR] get_usdt_pairs: {e}")
    return []
