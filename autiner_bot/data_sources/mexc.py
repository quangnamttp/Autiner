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
# Top tín hiệu (lọc coin tốt)
# =============================
async def get_top_signals(limit: int = 10):
    """
    Lấy danh sách coin biến động mạnh nhất để bot tạo tín hiệu trade.
    - Lọc coin rác (thanh khoản thấp).
    - Chuẩn bị dữ liệu cơ bản (RSI, MA).
    """
    try:
        url = S.MEXC_TICKER_URL
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                data = await resp.json()
                if data.get("success") and "data" in data:
                    coins = data["data"]

                    # Chỉ lấy USDT pair và bỏ coin thanh khoản thấp
                    filtered = []
                    for c in coins:
                        if not c["symbol"].endswith("_USDT"):
                            continue
                        volume = float(c.get("volume", 0))
                        if volume < 100_000:  # lọc coin rác
                            continue

                        change_pct = float(c.get("riseFallRate", 0))
                        filtered.append({
                            "symbol": c["symbol"],
                            "lastPrice": float(c.get("lastPrice", 0)),
                            "volume": volume,
                            "change_pct": change_pct,
                            "rsi": 50 + (change_pct * 2),   # RSI cơ bản demo
                            "ma_signal": "BUY" if change_pct > 0 else "SELL"
                        })

                    # Sort theo % biến động mạnh
                    sorted_coins = sorted(filtered, key=lambda x: abs(x["change_pct"]), reverse=True)
                    return sorted_coins[:limit]
    except Exception as e:
        print(f"[ERROR] get_top_signals: {e}")

    return []
