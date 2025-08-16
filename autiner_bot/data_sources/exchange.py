import aiohttp
from autiner_bot.settings import S

# =============================
# Lấy tỷ giá USDT/VND từ MEXC
# =============================
async def get_usdt_vnd_rate():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(S.MEXC_TICKER_VNDC_URL, timeout=10) as resp:
                data = await resp.json()
                if "data" in data:
                    return float(data["data"][0]["last"])
    except Exception as e:
        print(f"[ERROR] get_usdt_vnd_rate: {e}")
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
    except Exception as e:
        print(f"[ERROR] get_market_sentiment: {e}")
    return {"long": 0.0, "short": 0.0}
