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
                        "volume": float(t.get("amount24", 0)),
                        "change_pct": float(t.get("riseFallRate", 0)) * 100
                    })

                coins.sort(key=lambda x: x["volume"], reverse=True)
                return coins[:limit]
    except Exception as e:
        print(f"[ERROR] get_top20_futures: {e}")
        print(traceback.format_exc())
        return []


# =============================
# Lấy tỷ giá USDT/VND từ Binance P2P
# =============================
async def get_usdt_vnd_rate() -> float:
    url = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"
    payload = {
        "asset": "USDT",
        "fiat": "VND",
        "merchantCheck": False,
        "page": 1,
        "rows": 10,
        "tradeType": "SELL"
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=10) as resp:
                if resp.status != 200:
                    print(f"[ERROR] get_usdt_vnd_rate: HTTP {resp.status}")
                    return 0
                data = await resp.json()
                advs = data.get("data", [])
                if not advs:
                    return 0
                prices = [float(ad["adv"]["price"]) for ad in advs[:5] if "adv" in ad]
                return sum(prices) / len(prices) if prices else 0
    except Exception as e:
        print(f"[ERROR] get_usdt_vnd_rate: {e}")
        return 0


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
# Market sentiment (đơn giản: long/short % theo coin tăng/giảm)
# =============================
async def get_market_sentiment():
    try:
        coins = await get_top20_futures(limit=50)
        if not coins:
            return {"long": 50, "short": 50}
        ups = sum(1 for c in coins if c["change_pct"] >= 0)
        downs = len(coins) - ups
        total = max(1, ups + downs)
        return {
            "long": round(ups / total * 100, 2),
            "short": round(downs / total * 100, 2)
        }
    except Exception:
        return {"long": 50, "short": 50}


# =============================
# Signal Generator V2 (pro)
# =============================
async def analyze_coin_signal_v2(coin: dict) -> dict | None:
    symbol = coin["symbol"]
    last_price = coin["lastPrice"]
    change_pct = coin["change_pct"]
    volume = coin.get("volume", 0)

    # 1. Lọc coin rác (chỉ lọc giá siêu nhỏ)
    if last_price < 0.001:
        return None

    closes = await fetch_klines(symbol, limit=100)
    if not closes or len(closes) < 30:
        return None

    # 2. Indicators
    rsi = calculate_rsi(closes, 14)
    ma5, ma20, ma50 = np.mean(closes[-5:]), np.mean(closes[-20:]), np.mean(closes[-50:])

    trend = "LONG" if (ma5 > ma20 and change_pct > 0) else "SHORT"
    side = trend

    # RSI cực đoan đảo chiều
    if side == "LONG" and rsi > 75:
        side = "SHORT"
    elif side == "SHORT" and rsi < 25:
        side = "LONG"

    # 3. ATR
    highs = np.array(closes[-20:]) * 1.002
    lows = np.array(closes[-20:]) * 0.998
    tr = np.maximum(highs - lows,
                    np.abs(highs - closes[-2]),
                    np.abs(lows - closes[-2]))
    atr = np.mean(tr) if len(tr) > 0 else last_price * 0.005

    entry_price = last_price
    if side == "LONG":
        tp_price, sl_price = entry_price + 2 * atr, entry_price - 1.5 * atr
    else:
        tp_price, sl_price = entry_price - 2 * atr, entry_price + 1.5 * atr

    # 4. Strength
    strength = 45  # base thấp để luôn ra tín hiệu
    if abs(change_pct) >= 2:
        strength += 15
    if volume >= 5_000_000:
        strength += 10
    if side == "LONG" and rsi < 35:
        strength += 10
    if side == "SHORT" and rsi > 65:
        strength += 10
    if (ma5 > ma20 > ma50 and side == "LONG") or (ma5 < ma20 < ma50 and side == "SHORT"):
        strength += 10

    ma_diff = abs(ma5 - ma20) / ma20 * 100
    if ma_diff < 0.2 and 40 < rsi < 60:
        strength -= 15
        reason_note = "⚠️ Sideways"
    else:
        reason_note = ""

    strength = min(100, max(30, strength))  # không dưới 30%

    # 5. Label
    if strength >= 70:
        label = "⭐ Tín hiệu mạnh"
    elif strength >= 55:
        label = "Tín hiệu"
    else:
        label = "⚠️ Tham khảo"

    return {
        "symbol": symbol,
        "direction": side,
        "orderType": "MARKET",
        "entry": round(entry_price, 4),
        "tp": round(tp_price, 4),
        "sl": round(sl_price, 4),
        "strength": strength,
        "reason": f"{label} | RSI={rsi:.1f} | MA5={ma5:.4f}, MA20={ma20:.4f}, MA50={ma50:.4f} "
                  f"| Δ {change_pct:.2f}% | Vol={volume:,} | Trend={trend} {reason_note}"
    }
