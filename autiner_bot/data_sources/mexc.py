import aiohttp
import numpy as np


# =============================
# Helper: gọi API an toàn + log
# =============================
async def safe_get_json(url: str, session, method="GET", payload=None, headers=None):
    try:
        if method == "POST":
            async with session.post(url, json=payload, headers=headers, timeout=10) as resp:
                text = await resp.text()
                if resp.status != 200:
                    print(f"[HTTP ERROR] {url} → {resp.status} | {text[:200]}")
                    return None
                return await resp.json()
        else:
            async with session.get(url, headers=headers, timeout=10) as resp:
                text = await resp.text()
                if resp.status != 200:
                    print(f"[HTTP ERROR] {url} → {resp.status} | {text[:200]}")
                    return None
                return await resp.json()
    except Exception as e:
        print(f"[EXCEPTION] {url} → {e}")
        return None


# =============================
# Chuẩn hóa symbol cho Futures
# =============================
def normalize_symbol(symbol: str) -> str:
    if not symbol.endswith("_UMCBL"):
        return symbol.replace("_USDT", "_USDT_UMCBL")
    return symbol


# =============================
# Lấy tỷ giá USDT/VND từ Binance P2P
# =============================
async def get_usdt_vnd_rate():
    try:
        url = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"
        payload = {"asset": "USDT", "fiat": "VND", "tradeType": "BUY", "page": 1, "rows": 1, "payTypes": []}
        headers = {"Content-Type": "application/json"}
        async with aiohttp.ClientSession() as session:
            data = await safe_get_json(url, session, method="POST", payload=payload, headers=headers)
            if data and "data" in data and len(data["data"]) > 0:
                return float(data["data"][0]["adv"]["price"])
    except Exception as e:
        print(f"[ERROR] get_usdt_vnd_rate (Binance): {e}")
    return 25000.0


# =============================
# Sentiment thị trường (MEXC API)
# =============================
async def get_market_sentiment():
    try:
        url = "https://contract.mexc.com/api/v1/contract/ticker"
        async with aiohttp.ClientSession() as session:
            data = await safe_get_json(url, session)
            if data and data.get("success") and "data" in data:
                coins = data["data"]
                long_vol, short_vol = 0, 0
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
                    return {"long": round(long_vol / total * 100, 2), "short": round(short_vol / total * 100, 2)}
    except Exception as e:
        print(f"[ERROR] get_market_sentiment: {e}")
    return {"long": 50.0, "short": 50.0}


# =============================
# Funding + Volume
# =============================
async def get_market_funding_volume():
    try:
        url = "https://contract.mexc.com/api/v1/contract/funding_rate"
        async with aiohttp.ClientSession() as session:
            data = await safe_get_json(url, session)
            if data and data.get("success") and "data" in data:
                all_data = data["data"]
                rates = [float(c.get("fundingRate", 0)) for c in all_data if "fundingRate" in c]
                avg_funding = sum(rates) / len(rates) if rates else 0
                total_vol = sum(float(c.get("volume", 0)) for c in all_data if "volume" in c)
                return {"funding": f"{avg_funding * 100:.4f}%", "volume": f"{total_vol:,.0f}", "trend": "Tăng" if avg_funding > 0 else "Giảm"}
    except Exception as e:
        print(f"[ERROR] get_market_funding_volume: {e}")
    return {"funding": "N/A", "volume": "N/A", "trend": "N/A"}


# =============================
# Top Futures (lọc giá + volume)
# =============================
async def get_top20_futures(limit: int = 20, min_price: float = 0.01, min_volume: float = 100000):
    try:
        url = "https://contract.mexc.com/api/v1/contract/ticker"
        async with aiohttp.ClientSession() as session:
            data = await safe_get_json(url, session)
            if data and data.get("success") and "data" in data:
                filtered = []
                for c in data["data"]:
                    if not c["symbol"].endswith("_USDT"):
                        continue

                    last_price = float(c.get("lastPrice", 0))
                    volume = float(c.get("volume", 0))

                    # Bộ lọc giá & volume
                    if last_price < min_price:
                        continue
                    if volume < min_volume:
                        continue

                    filtered.append({
                        "symbol": c["symbol"],
                        "lastPrice": last_price,
                        "volume": volume,
                        "change_pct": float(c.get("riseFallRate", 0))
                    })
                return sorted(filtered, key=lambda x: x["volume"], reverse=True)[:limit]
    except Exception as e:
        print(f"[ERROR] get_top20_futures: {e}")
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
# Kline
# =============================
async def fetch_klines(symbol: str, limit: int = 100):
    sym = normalize_symbol(symbol)
    url = f"https://contract.mexc.com/api/v1/contract/kline/{sym}?interval=Min1&limit={limit}"
    try:
        async with aiohttp.ClientSession() as session:
            data = await safe_get_json(url, session)
            if not data or not data.get("success") or not data.get("data"):
                return []
            return [float(c[4]) for c in data["data"]][-limit:]
    except Exception as e:
        print(f"[EXCEPTION] fetch_klines {symbol}: {e}")
    return []


# =============================
# Phân tích tín hiệu V3 (RSI + MA + Volume)
# =============================
async def analyze_coin_signal_v2(coin: dict) -> dict:
    symbol = coin["symbol"]
    last_price = coin["lastPrice"]
    change_pct = coin["change_pct"]
    volume = coin.get("volume", 0)

    if last_price <= 0:
        return {"symbol": symbol, "direction": "LONG", "orderType": "MARKET", "entry": 0, "tp": 0, "sl": 0, "strength": 0, "reason": "⚠️ Không có dữ liệu giá hợp lệ"}

    closes = await fetch_klines(symbol, limit=100)
    if not closes or len(closes) < 20:
        return {"symbol": symbol, "direction": "LONG", "orderType": "MARKET", "entry": 0, "tp": 0, "sl": 0, "strength": 0, "reason": "⚠️ Không có dữ liệu Kline"}

    rsi = calculate_rsi(closes, 14)
    ma5, ma20 = np.mean(closes[-5:]), np.mean(closes[-20:])

    # Trend chính
    if change_pct > 0 and ma5 > ma20:
        side = "LONG"
    elif change_pct < 0 and ma5 < ma20:
        side = "SHORT"
    else:
        side = "LONG" if change_pct >= 0 else "SHORT"

    # Đảo chiều khi RSI cực đoan + volume lớn
    if side == "LONG":
        if rsi > 75 and ma5 < ma20 and volume > 10_000_000:
            side = "SHORT"
    elif side == "SHORT":
        if rsi < 25 and ma5 > ma20 and volume > 10_000_000:
            side = "LONG"

    # ATR → TP/SL
    highs = np.array(closes[-20:]) * 1.002
    lows = np.array(closes[-20:]) * 0.998
    tr = np.maximum(highs - lows, np.abs(highs - closes[-2]), np.abs(lows - closes[-2]))
    atr = np.mean(tr) if len(tr) > 0 else last_price * 0.005

    entry_price = last_price
    if side == "LONG":
        tp_price, sl_price = entry_price + 2 * atr, entry_price - 1 * atr
    else:
        tp_price, sl_price = entry_price - 2 * atr, entry_price + 1 * atr

    # Strength
    strength = 60
    if abs(change_pct) > 3:
        strength += 10
    if volume > 10_000_000:
        strength += 10
    if (side == "LONG" and rsi < 25 and ma5 > ma20 and volume > 10_000_000) or \
       (side == "SHORT" and rsi > 75 and ma5 < ma20 and volume > 10_000_000):
        strength += 15
    strength = min(100, strength)

    return {
        "symbol": symbol,
        "direction": side,
        "orderType": "MARKET",
        "entry": round(entry_price, 4),
        "tp": round(tp_price, 4),
        "sl": round(sl_price, 4),
        "strength": strength,
        "reason": f"RSI={rsi:.1f} | MA5={ma5:.4f}, MA20={ma20:.4f} | Biến động {change_pct:.2f}% | Volume {volume:,}"
    }
