# autiner_bot/data_sources/mexc.py
import aiohttp
from autiner_bot.settings import S

# =============================
# Hàm fetch chung
# =============================
async def fetch_json(url: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            return await resp.json()

# =============================
# Lấy toàn bộ tickers futures
# =============================
async def get_all_tickers():
    """Lấy tất cả tickers futures từ MEXC."""
    try:
        data = await fetch_json(S.MEXC_TICKER_URL)
        return data.get("data", [])
    except Exception as e:
        print(f"[ERROR] get_all_tickers: {e}")
        return []

# =============================
# Lấy top coin mạnh nhất
# =============================
async def get_top_moving_coins(limit=5):
    """
    Lấy coin futures biến động mạnh nhất & volume cao nhất.
    Ưu tiên volume + % biến động tại thời điểm hiện tại.
    """
    tickers = await get_all_tickers()
    futures = [t for t in tickers if t.get("symbol", "").endswith("_USDT")]

    ranked = []
    for f in futures:
        try:
            last_price = float(f.get("lastPrice", 0))
            volume = float(f.get("volume", 0))  # volume theo USDT
            rf = float(f.get("riseFallRate", 0))

            # % biến động
            change_pct = rf * 100 if abs(rf) < 10 else rf

            # Chỉ số xếp hạng = |% biến động| * volume
            score = abs(change_pct) * volume

            ranked.append({
                "symbol": f["symbol"],
                "lastPrice": last_price,
                "volume": volume,
                "change_pct": change_pct,
                "score": score
            })
        except:
            continue

    # Sắp xếp theo score giảm dần
    ranked.sort(key=lambda x: x["score"], reverse=True)

    return ranked[:limit]

# =============================
# Long/Short sentiment BTC
# =============================
async def get_market_sentiment():
    """Tỷ lệ Long/Short BTC."""
    try:
        url = "https://contract.mexc.com/api/v1/contract/long_short_account_ratio?symbol=BTC_USDT&period=5m"
        data = await fetch_json(url)
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
# Funding, volume, trend BTC
# =============================
async def get_market_funding_volume():
    """Funding, volume, xu hướng BTC."""
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
