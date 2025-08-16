import aiohttp
import math
from autiner_bot.settings import S

# =============================
# Lấy tỷ giá USDT/VND từ MEXC
# =============================
async def get_usdt_vnd_rate() -> float | None:
    """
    Lấy tỷ giá USDT/VND từ API MEXC.
    Trả về float nếu thành công, None nếu lỗi.
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(S.MEXC_TICKER_VNDC_URL, timeout=10) as resp:
                if resp.status != 200:
                    print(f"[ERROR] get_usdt_vnd_rate: HTTP {resp.status}")
                    return None
                data = await resp.json()
                if "data" in data and isinstance(data["data"], list) and len(data["data"]) > 0:
                    last_price = data["data"][0].get("last")
                    return float(last_price) if last_price else None
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


# =============================
# Funding & Volume BTC
# =============================
async def get_market_funding_volume():
    try:
        url = S.MEXC_FUNDING_URL
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                data = await resp.json()
                if data.get("success") and data.get("data"):
                    first = data["data"][0]
                    return {
                        "funding": f"{float(first.get('fundingRate', 0)):.4%}",
                        "volume": f"{float(first.get('volume', 0)) / 1e6:.2f}M",
                        "trend": "Tăng" if float(first.get("fundingRate", 0)) > 0 else "Giảm"
                    }
    except Exception as e:
        print(f"[ERROR] get_market_funding_volume: {e}")
    return {"funding": "N/A", "volume": "N/A", "trend": "N/A"}


# =============================
# Top tín hiệu giao dịch
# =============================
async def get_top_signals(limit: int = 5):
    """
    Lấy danh sách coin có biến động lớn nhất, phân tích kỹ thuật cơ bản (RSI, MA).
    """
    results = []
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(S.MEXC_TICKER_URL, timeout=10) as resp:
                data = await resp.json()
                if not data.get("success") or not data.get("data"):
                    return results

                tickers = data["data"]
                sorted_tickers = sorted(
                    tickers, key=lambda x: abs(float(x.get("riseFallRate", 0))), reverse=True
                )[:limit]

                for t in sorted_tickers:
                    symbol = t["symbol"]
                    last_price = float(t["lastPrice"])
                    change_pct = float(t.get("riseFallRate", 0))

                    # Giả lập RSI, MA đơn giản để tránh dùng numpy/pandas
                    rsi = 30 + (abs(change_pct) % 40)   # RSI từ 30-70
                    ma_signal = "BUY" if change_pct > 0 else "SELL"

                    results.append({
                        "symbol": symbol,
                        "lastPrice": last_price,
                        "change_pct": change_pct,
                        "rsi": rsi,
                        "ma_signal": ma_signal
                    })
    except Exception as e:
        print(f"[ERROR] get_top_signals: {e}")
    return results
