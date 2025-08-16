import aiohttp

# =============================
# Lấy tỷ giá USDT/VND
# =============================
async def get_usdt_vnd_rate():
    urls = [
        "https://www.mexc.com/open/api/v2/market/ticker?symbol=USDT_VND",
        "https://api.binance.com/api/v3/ticker/price?symbol=USDTBUSD"
    ]
    async with aiohttp.ClientSession() as session:
        for url in urls:
            try:
                async with session.get(url, timeout=10) as resp:
                    data = await resp.json()
                    if "data" in data:
                        return float(data["data"][0]["last"])
                    if "price" in data:
                        return float(data["price"]) * 25000  # Binance backup
            except:
                continue
    return None

# =============================
# Sentiment thị trường BTC
# =============================
async def get_market_sentiment():
    try:
        url = "https://contract.mexc.com/api/v1/contract/long_short_account_ratio?symbol=BTC_USDT&period=5m"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                data = await resp.json()
                if data.get("success") and data.get("data"):
                    latest = data["data"][-1]
                    return {
                        "long": float(latest.get("longAccount", 0)),
                        "short": float(latest.get("shortAccount", 0))
                    }
    except:
        pass
    return {"long": 0.0, "short": 0.0}
