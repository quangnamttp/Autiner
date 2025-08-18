import aiohttp
import numpy as np
import traceback

MEXC_BASE_URL = "https://contract.mexc.com"

# =============================
# Lấy dữ liệu ticker Futures
# =============================
async def get_top20_futures(limit: int = 20):
    try:
        url = f"{MEXC_BASE_URL}/api/v1/contract/ticker"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                data = await resp.json()
                if not data or "data" not in data:
                    return []
                tickers = data["data"]

                coins = []
                for t in tickers:
                    if not t.get("symbol", "").endswith("_USDT"):
                        continue
                    coins.append({
                        "symbol": t["symbol"],
                        "lastPrice": float(t["lastPrice"]),
                        "volume": float(t["amount24"]) if t.get("amount24") else 0,
                        "change_pct": float(t.get("riseFallRate", 0)) * 100
                    })

                coins.sort(key=lambda x: x["volume"], reverse=True)
                return coins[:limit]
    except Exception as e:
        print(f"[ERROR] get_top20_futures: {e}")
        print(traceback.format_exc())
        return []


# =============================
# Lấy tỷ giá USDT/VND
# =============================
async def get_usdt_vnd_rate():
    try:
        url = "https://www.mexc.com/open/api/v2/market/ticker?symbol=USDT_VND"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                data = await resp.json()
                if "data" in data and len(data["data"]) > 0:
                    return float(data["data"][0]["last"])
        return None
    except Exception as e:
        print(f"[ERROR] get_usdt_vnd_rate: {e}")
        return None


# =============================
# Lấy Kline để phân tích
# =============================
async def fetch_klines(symbol: str, limit: int = 100):
    try:
        url = f"{MEXC_BASE_URL}/api/v1/contract/kline/{symbol}?interval=Min1&limit={limit}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                data = await resp.json()
                if "data" not in data:
                    return []
                return [float(k[4]) for k in data["data"]]  # close price
    except Exception as e:
        print(f"[ERROR] fetch_klines({symbol}): {e}")
        return []


# =============================
# RSI
# =============================
def calculate_rsi(closes, period=14):
    if len(closes) < period + 1:
        return 50
    deltas = np.diff(closes)
    ups = deltas[deltas > 0].sum() / period
    downs = -deltas[deltas < 0].sum() / period
    rs = ups / downs if downs != 0 else 0
    return 100 - (100 / (1 + rs))


# =============================
# Market sentiment (giả lập)
# =============================
async def get_market_sentiment():
    return {"long": 55, "short": 45}


# =============================
# Signal Generator V2
# =============================
async def analyze_coin_signal_v2(coin: dict) -> dict:
    """Phân tích tín hiệu: RSI + MA + Volume (luôn trả về)"""
    symbol = coin["symbol"]
    last_price = coin["lastPrice"]
    change_pct = coin["change_pct"]
    volume = coin.get("volume", 0)

    # Nếu coin quá rác thì vẫn cho tín hiệu nhưng cảnh báo
    if last_price < 0.001:
        return {
            "symbol": symbol,
            "direction": "N/A",
            "entry": last_price,
            "tp": last_price,
            "sl": last_price,
            "strength": 10,
            "orderType": "MARKET",
            "reason": "⚠️ Coin rác giá <0.001"
        }

    closes = await fetch_klines(symbol, limit=100)

    # Nếu thiếu dữ liệu Kline → vẫn trả về tín hiệu yếu
    if not closes or len(closes) < 20:
        side = "LONG" if change_pct >= 0 else "SHORT"
        return {
            "symbol": symbol,
            "direction": side,
            "entry": round(last_price, 4),
            "tp": round(last_price * (1.01 if side == "LONG" else 0.99), 4),
            "sl": round(last_price * (0.99 if side == "LONG" else 1.01), 4),
            "strength": 40,
            "orderType": "MARKET",
            "reason": "⚠️ Thiếu dữ liệu Kline - chỉ gợi ý tham khảo"
        }

    # Nếu có dữ liệu đủ thì tính RSI + MA
    rsi = calculate_rsi(closes, 14)
    ma5, ma20 = np.mean(closes[-5:]), np.mean(closes[-20:])
    trend = "LONG" if change_pct >= 0 and ma5 >= ma20 else "SHORT"
    side = trend

    highs = np.array(closes[-20:]) * 1.002
    lows = np.array(closes[-20:]) * 0.998
    tr = np.maximum(highs - lows, np.abs(highs - closes[-2]), np.abs(lows - closes[-2]))
    atr = np.mean(tr) if len(tr) > 0 else last_price * 0.005

    entry_price = last_price
    if side == "LONG":
        tp_price, sl_price = entry_price + 2 * atr, entry_price - 1 * atr
    else:
        tp_price, sl_price = entry_price - 2 * atr, entry_price + 1 * atr

    # =============================
    # Strength scoring
    # =============================
    strength = 50
    if abs(change_pct) > 3:
        strength += 10
    if volume > 5_000_000:   # hạ ngưỡng volume
        strength += 10
    if side == "LONG" and rsi < 30:
        strength += 15
    if side == "SHORT" and rsi > 70:
        strength += 15

    ma_diff = abs(ma5 - ma20) / ma20 * 100
    reason_note = ""
    if ma_diff < 0.3:
        strength -= 15
        reason_note = " | ⚠️ Sideways (MA5≈MA20)"

    strength = min(100, max(0, strength))

    if strength >= 70:
        label = "⭐ Tín hiệu mạnh"
    elif strength >= 55:
        label = "Tín hiệu"
    else:
        label = "Tham khảo"

    return {
        "symbol": symbol,
        "direction": side,
        "orderType": "MARKET",
        "entry": round(entry_price, 4),
        "tp": round(tp_price, 4),
        "sl": round(sl_price, 4),
        "strength": strength,
        "reason": f"{label} | RSI={rsi:.1f} | MA5={ma5:.4f}, MA20={ma20:.4f} | Δ {change_pct:.2f}% | Vol {volume:,} | Trend={trend}{reason_note}"
    }
