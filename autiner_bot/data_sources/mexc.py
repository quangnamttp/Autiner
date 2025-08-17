import aiohttp
import numpy as np
from autiner_bot.settings import S


# =============================
# Lấy tỷ giá USDT/VND từ Binance P2P
# =============================
async def get_usdt_vnd_rate():
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

    return 25000.0


# =============================
# Sentiment thị trường (Long/Short theo volume)
# =============================
async def get_market_sentiment():
    try:
        url = S.MEXC_TICKER_URL
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                data = await resp.json()
                if data.get("success") and "data" in data:
                    coins = data["data"]

                    long_vol = 0
                    short_vol = 0

                    for c in coins:
                        if not c["symbol"].endswith("_USDT"):
                            continue
                        vol = float(c.get("volume", 0))
                        change_pct = float(c.get("riseFallRate", 0))

                        if change_pct >= 0:
                            long_vol += vol
                        else:
                            short_vol += vol

                    total = long_vol + short_vol
                    if total > 0:
                        long_pct = (long_vol / total) * 100
                        short_pct = (short_vol / total) * 100
                    else:
                        long_pct, short_pct = 50.0, 50.0

                    return {"long": round(long_pct, 2), "short": round(short_pct, 2)}
    except Exception as e:
        print(f"[ERROR] get_market_sentiment: {e}")

    return {"long": 50.0, "short": 50.0}


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
                        "funding": f"{float(latest.get('fundingRate', 0)) * 100:.4f}%",
                        "volume": latest.get("volume", "N/A"),
                        "trend": "Tăng" if float(latest.get("fundingRate", 0)) > 0 else "Giảm"
                    }
    except Exception as e:
        print(f"[ERROR] get_market_funding_volume: {e}")
    return {"funding": "N/A", "volume": "N/A", "trend": "N/A"}


# =============================
# Top 20 Futures theo Volume
# =============================
async def get_top20_futures(limit: int = 20):
    try:
        url = S.MEXC_TICKER_URL
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                data = await resp.json()
                if data.get("success") and "data" in data:
                    coins = data["data"]

                    filtered = []
                    for c in coins:
                        if not c["symbol"].endswith("_USDT"):
                            continue
                        volume = float(c.get("volume", 0))
                        change_pct = float(c.get("riseFallRate", 0))
                        filtered.append({
                            "symbol": c["symbol"],
                            "lastPrice": float(c.get("lastPrice", 0)),
                            "volume": volume,
                            "change_pct": change_pct
                        })

                    sorted_coins = sorted(filtered, key=lambda x: x["volume"], reverse=True)
                    return sorted_coins[:limit]
    except Exception as e:
        print(f"[ERROR] get_top20_futures: {e}")

    return []


# =============================
# Detect trend (top coin mạnh nhất)
# =============================
async def detect_trend(limit: int = 5):
    try:
        coins = await get_top20_futures(limit=20)
        if not coins:
            return []
        sorted_by_change = sorted(coins, key=lambda x: abs(x["change_pct"]), reverse=True)
        return sorted_by_change[:limit]
    except Exception as e:
        print(f"[ERROR] detect_trend: {e}")
        return []


# =============================
# RSI
# =============================
def calculate_rsi(prices, period: int = 14) -> float:
    if len(prices) < period + 1:
        return 50.0
    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])
    if avg_loss == 0:
        return 100.0
    if avg_gain == 0:
        return 0.0
    rs = avg_gain / avg_loss
    return float(100 - (100 / (1 + rs)))


# =============================
# Lấy dữ liệu Kline
# =============================
async def fetch_klines(symbol: str, limit: int = 100):
    url = S.MEXC_KLINES_URL.format(sym=symbol)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                data = await resp.json()
                if data.get("success") and "data" in data:
                    closes = [float(c[4]) for c in data["data"]]
                    return closes[-limit:]
    except Exception as e:
        print(f"[ERROR] fetch_klines {symbol}: {e}")
    return []


# =============================
# Phân tích tín hiệu V2
# =============================
async def analyze_coin_signal_v2(coin: dict) -> dict:
    symbol = coin["symbol"]
    last_price = coin["lastPrice"]
    change_pct = coin["change_pct"]
    volume = coin.get("volume", 0)

    closes = await fetch_klines(symbol, limit=100)
    if not closes:
        closes = [last_price] * 20

    rsi = calculate_rsi(closes, 14)
    if rsi > 70:
        rsi_signal = "QUÁ MUA (SELL)"
    elif rsi < 30:
        rsi_signal = "QUÁ BÁN (BUY)"
    else:
        rsi_signal = "TRUNG LẬP"

    ma5 = np.mean(closes[-5:]) if len(closes) >= 5 else last_price
    ma20 = np.mean(closes[-20:]) if len(closes) >= 20 else last_price
    ma_signal = "BUY" if ma5 > ma20 else "SELL"

    if rsi < 30 or (ma5 > ma20 and change_pct > 0):
        side = "LONG"
    elif rsi > 70 or (ma5 < ma20 and change_pct < 0):
        side = "SHORT"
    else:
        side = "LONG" if change_pct >= 0 else "SHORT"

    if abs(change_pct) > 2:
        order_type = "MARKET"
        entry_price = last_price
    else:
        order_type = "LIMIT"
        entry_price = min(ma5, last_price) if side == "LONG" else max(ma5, last_price)

    highs = np.array(closes[-20:]) * (1 + 0.002)
    lows = np.array(closes[-20:]) * (1 - 0.002)
    tr = np.maximum(highs - lows, np.abs(highs - closes[-2]), np.abs(lows - closes[-2]))
    atr = np.mean(tr) if len(tr) > 0 else last_price * 0.005

    if side == "LONG":
        tp_price = entry_price + 2 * atr
        sl_price = entry_price - 1 * atr
    else:
        tp_price = entry_price - 2 * atr
        sl_price = entry_price + 1 * atr

    tp_pct = (tp_price / entry_price - 1) * 100
    sl_pct = (sl_price / entry_price - 1) * 100

    strength = 50
    if abs(change_pct) > 3:
        strength += 20
    if side == "LONG" and rsi < 25:
        strength += 15
    if side == "SHORT" and rsi > 75:
        strength += 15
    if volume > 10_000_000:
        strength += 10
    strength = min(100, max(50, strength))

    return {
        "symbol": symbol,
        "direction": side,
        "orderType": order_type,
        "entry": round(entry_price, 4),
        "tp": round(tp_price, 4),
        "sl": round(sl_price, 4),
        "tp_pct": round(tp_pct, 2),
        "sl_pct": round(sl_pct, 2),
        "strength": strength,
        "reason": f"RSI {rsi_signal} ({rsi:.1f}) | MA {ma_signal} "
                  f"(MA5={ma5:.4f}, MA20={ma20:.4f}) | ATR={atr:.4f} "
                  f"| Biến động {change_pct:.2f}% | Volume {volume}"
    }
