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
    Lấy coin Futures tốt nhất:
    - Volume cao
    - Biến động mạnh
    - Hướng nến rõ ràng
    """
    tickers = await get_all_tickers()
    futures = [t for t in tickers if t.get("symbol", "").endswith("_USDT")]

    scored = []
    for f in futures:
        try:
            last_price = float(f.get("lastPrice", 0))
            volume = float(f.get("volume", 0))
            change_pct = float(f.get("riseFallRate", 0)) * 100 if abs(float(f.get("riseFallRate", 0))) < 10 else float(f.get("riseFallRate", 0))

            if volume < 500_000:  # loại coin volume thấp
                continue

            score = abs(change_pct) * (volume / 1_000_000)  # điểm = biến động * volume(M USDT)
            scored.append({
                "symbol": f["symbol"],
                "lastPrice": last_price,
                "change_pct": change_pct,
                "volume": volume,
                "score": score
            })
        except:
            continue

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:limit]
