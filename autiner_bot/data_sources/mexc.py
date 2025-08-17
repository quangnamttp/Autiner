# autiner_bot/data_sources/mexc.py
import aiohttp
from autiner_bot.settings import S

# =============================
# Lấy tỷ giá USDT/VND từ Binance P2P
# =============================
async def get_usdt_vnd_rate():
    """
    Lấy tỷ giá USDT/VND từ Binance P2P (ổn định hơn MEXC/Coingecko).
    """
    try:
        url = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"
        payload = {
            "asset": "USDT",
            "fiat": "VND",
            "tradeType": "BUY",
            "page": 1,
            "rows": 1,
            "payTypes": []
        }
        headers = {"Content-Type": "application/json"}

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers, timeout=10) as resp:
                data = await resp.json()
                if "data" in data and len(data["data"]) > 0:
                    price = float(data["data"][0]["adv"]["price"])
                    return price
    except Exception as e:
        print(f"[ERROR] get_usdt_vnd_rate (Binance): {e}")

    # fallback cuối cùng nếu lỗi
    return 25000.0


# =============================
# Sentiment thị trường BTC
# =============================
async def get_market_sentiment():
    """
    Lấy tỷ lệ Long/Short của BTC Futures trên MEXC.
    """
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


# =============================
# Funding + Volume
# =============================
async def get_market_funding_volume():
    """
    Lấy funding rate và volume tổng từ MEXC Futures.
    """
    try:
        url = S.MEXC_FUNDING_URL
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                data = await resp.json()
                if data.get("success") and "data" in data:
                    latest = data["data"][0]
                    return {
                        "funding": f"{float(latest.get('fundingRate', 0))*100:.4f}%",
                        "volume": latest.get("volume", "N/A"),
                        "trend": "Tăng" if float(latest.get("fundingRate", 0)) > 0 else "Giảm"
                    }
    except Exception as e:
        print(f"[ERROR] get_market_funding_volume: {e}")
    return {"funding": "N/A", "volume": "N/A", "trend": "N/A"}
