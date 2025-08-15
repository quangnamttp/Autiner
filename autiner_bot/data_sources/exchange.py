import aiohttp
from autiner_bot.settings import S

async def fetch_json(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            return await resp.json()

async def get_usdt_vnd_rate():
    """Lấy tỷ giá USDT → VND từ MEXC."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(S.MEXC_TICKER_VNDC_URL) as resp:
                data = await resp.json()
                ticker = data.get("data", [])[0]
                return float(ticker["last"])
    except:
        return None

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

        tickers_url = S.MEXC_TICKER_URL
        tickers = await fetch_json(tickers_url)
        tickers = tickers.get("data", [])
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
