# autiner_bot/data_sources/mexc.py
import aiohttp
import traceback

from autiner_bot.settings import S


# =============================
# Lấy tỷ giá USDT/VND
# =============================
async def get_usdt_vnd_rate() -> float | None:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(S.MEXC_TICKER_VNDC_URL, timeout=10) as resp:
                data = await resp.json()
                if data and "data" in data:
                    ticker = data["data"][0]
                    return float(ticker.get("last", 0))
    except Exception as e:
        print(f"[ERROR] get_usdt_vnd_rate: {e}")
        print(traceback.format_exc())
    return None


# =============================
# Lấy top futures
# =============================
async def get_top20_futures(limit: int = 20) -> list[dict]:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(S.MEXC_TICKER_URL, timeout=10) as resp:
                data = await resp.json()
                if not data or "data" not in data:
                    return []
                tickers = data["data"]
                tickers.sort(key=lambda x: float(x.get("volume", 0)), reverse=True)
                top = tickers[:limit]
                result = []
                for t in top:
                    result.append({
                        "symbol": t.get("symbol"),
                        "price": float(t.get("lastPrice", 0)),
                        "volume": float(t.get("volume", 0)),
                        "change_pct": float(t.get("riseFallRate", 0))
                    })
                return result
    except Exception as e:
        print(f"[ERROR] get_top20_futures: {e}")
        print(traceback.format_exc())
        return []


# =============================
# Funding rate
# =============================
async def get_funding_rate(symbol: str = "BTC_USDT") -> float | None:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(S.MEXC_FUNDING_URL, timeout=10) as resp:
                data = await resp.json()
                if not data or "data" not in data:
                    return None
                for item in data["data"]:
                    if item.get("symbol") == symbol:
                        return float(item.get("fundingRate", 0)) * 100
    except Exception as e:
        print(f"[ERROR] get_funding_rate: {e}")
        print(traceback.format_exc())
    return None


# =============================
# Phân tích tín hiệu coin
# =============================
async def analyze_coin_signal_v2(coin: dict) -> dict:
    try:
        symbol = coin.get("symbol", "UNKNOWN")
        price = coin.get("price", 0)
        change = coin.get("change_pct", 0)

        direction = "LONG" if change >= 0 else "SHORT"
        order_type = "Limit" if abs(change) < 3 else "Market"
        entry = price
        tp = price * (1.01 if direction == "LONG" else 0.99)
        sl = price * (0.99 if direction == "LONG" else 1.01)
        strength = min(100, max(50, int(abs(change) * 10)))
        reason = f"{symbol} biến động {change:.2f}% → {direction}"

        return {
            "symbol": symbol,
            "direction": direction,
            "orderType": order_type,
            "entry": entry,
            "tp": tp,
            "sl": sl,
            "strength": strength,
            "reason": reason
        }
    except Exception as e:
        print(f"[ERROR] analyze_coin_signal_v2: {e}")
        print(traceback.format_exc())
        return {}


# =============================
# Funding + Volume chung
# =============================
async def get_market_funding_volume() -> dict:
    try:
        coins = await get_top20_futures(limit=20)
        total_volume = sum([c.get("volume", 0) for c in coins])
        total_volume_bil = total_volume / 1e9

        funding = await get_funding_rate("BTC_USDT")

        return {
            "funding": f"{funding:.4f}%" if funding else "N/A",
            "volume": f"{total_volume_bil:.1f}B"
        }
    except Exception as e:
        print(f"[ERROR] get_market_funding_volume: {e}")
        print(traceback.format_exc())
        return {"funding": "N/A", "volume": "N/A"}
