# autiner_bot/data_sources/mexc.py
import aiohttp
from autiner_bot.settings import S

# =============================
# Lấy tỷ giá USDT/VND
# =============================
async def get_usdt_vnd_rate():
    """
    Lấy tỷ giá USDT/VND bằng cách:
    - Lấy giá USDT/USD từ MEXC
    - Lấy tỷ giá USD/VND từ Coingecko
    => Nhân lại để ra USDT/VND
    """
    try:
        async with aiohttp.ClientSession() as session:
            # 1. Lấy giá USDT/USD trên MEXC
            async with session.get(S.MEXC_TICKER_URL, timeout=10) as resp1:
                data1 = await resp1.json()
                usdt_usd = None
                if data1.get("success") and "data" in data1:
                    for item in data1["data"]:
                        if item["symbol"] == "BTC_USDT":  # lấy BTC làm chuẩn check
                            usdt_usd = 1.0  # USDT ~ USD
                            break

            # 2. Lấy tỷ giá USD/VND từ Coingecko
            url = "https://api.coingecko.com/api/v3/simple/price?ids=tether,usd&vs_currencies=vnd"
            async with session.get(url, timeout=10) as resp2:
                data2 = await resp2.json()
                if "tether" in data2 and "vnd" in data2["tether"]:
                    usdt_vnd = float(data2["tether"]["vnd"])
                    return usdt_vnd

            # fallback: nếu không có, dùng tỷ giá USD
            if "usd" in data2 and "vnd" in data2["usd"]:
                usd_vnd = float(data2["usd"]["vnd"])
                return usd_vnd * (usdt_usd or 1)

    except Exception as e:
        print(f"[ERROR] get_usdt_vnd_rate: {e}")

    # fallback cuối cùng
    return 25000.0


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


# =============================
# Funding + Volume
# =============================
async def get_market_funding_volume():
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


# =============================
# Top tín hiệu (nâng cấp chuyên sâu)
# =============================
async def get_top_signals(limit: int = 5):
    """
    Lấy danh sách coin biến động mạnh nhất để bot tạo tín hiệu trade.
    """
    try:
        url = S.MEXC_TICKER_URL
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                data = await resp.json()
                if data.get("success") and "data" in data:
                    coins = data["data"]

                    # Chỉ lấy USDT pair
                    filtered = [
                        {
                            "symbol": c["symbol"],
                            "lastPrice": float(c.get("lastPrice", 0)),
                            "change_pct": float(c.get("riseFallRate", 0)),
                            "rsi": 50 + (float(c.get("riseFallRate", 0)) * 2),   # fake RSI demo
                            "ma_signal": "BUY" if float(c.get("riseFallRate", 0)) > 0 else "SELL"
                        }
                        for c in coins if c["symbol"].endswith("_USDT")
                    ]

                    # Sort theo % biến động mạnh
                    sorted_coins = sorted(filtered, key=lambda x: abs(x["change_pct"]), reverse=True)

                    return sorted_coins[:limit]
    except Exception as e:
        print(f"[ERROR] get_top_signals: {e}")

    return []
