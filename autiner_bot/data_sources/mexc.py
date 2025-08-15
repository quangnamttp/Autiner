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
    """
    tickers = await get_all_tickers()
    futures = [t for t in tickers if t.get("symbol", "").endswith("_USDT")]

    for f in futures:
        try:
            last_price = float(f["lastPrice"])
            # Dùng riseFallRate (MEXC trả %) để chính xác hơn
            change_pct = float(f.get("riseFallRate", 0)) * 100 if abs(float(f.get("riseFallRate", 0))) < 10 else float(f.get("riseFallRate", 0))
            f["change_pct"] = change_pct
            f["lastPrice"] = last_price
        except:
            f["change_pct"] = 0
            f["lastPrice"] = 0

    futures.sort(key=lambda x: abs(x["change_pct"]), reverse=True)
    return futures[:limit]

async def get_market_sentiment():
    """Lấy tỷ lệ Long/Short từ MEXC (BTC_USDT)."""
    try:
        url = "https://contract.mexc.com/api/v1/contract/long_short_account_ratio?symbol=BTC_USDT&period=5m"
        data = await fetch_json(url)
        if data.get("success") and data.get("data"):
            latest = data["data"][-1]
            long_ratio = float(latest.get("longAccount", 0))
            short_ratio = float(latest.get("shortAccount", 0))
            return {"long": long_ratio, "short": short_ratio}
    except Exception as e:
        print(f"[ERROR] get_market_sentiment: {e}")
    return {"long": 0.0, "short": 0.0}

async def get_market_funding_volume():
    """Lấy funding rate, volume và xu hướng thị trường từ MEXC."""
    try:
        funding_url = "https://contract.mexc.com/api/v1/contract/funding_rate?symbol=BTC_USDT"
        funding_data = await fetch_json(funding_url)
        funding_rate = funding_data.get("data", {}).get("fundingRate", "0%")

        tickers = await get_all_tickers()
        volume = "N/A"
        trend = "N/A"
        for item in tickers:
            if item.get("symbol") == "BTC_USDT":
                volume = f"{float(item.get('volume', 0)) / 1_000_000:.2f}M USDT"
                change_pct = float(item.get("riseFallRate", 0))
                trend = "📈 Tăng" if change_pct > 0 else "📉 Giảm" if change_pct < 0 else "➖ Đi ngang"
                break

        return {
            "funding": funding_rate,
            "volume": volume,
            "trend": trend
        }
    except Exception as e:
        print(f"[ERROR] get_market_funding_volume: {e}")
    return {"funding": "0%", "volume": "N/A", "trend": "N/A"}
