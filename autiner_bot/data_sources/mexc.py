import aiohttp
import numpy as np
import traceback

MEXC_BASE_URL = "https://contract.mexc.com"

# =============================
# Lấy dữ liệu ticker Futures (top 30)
# =============================
async def get_top30_futures(limit: int = 30):
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
                    last_price = float(t["lastPrice"])
                    if last_price < 0.01:  # bỏ coin rác
                        continue
                    coins.append({
                        "symbol": t["symbol"],
                        "lastPrice": last_price,
                        "volume": float(t.get("amount24", 0)),
                        "change_pct": float(t.get("riseFallRate", 0)) * 100
                    })

                coins.sort(key=lambda x: x["volume"], reverse=True)
                return coins[:limit]
    except Exception as e:
        print(f"[ERROR] get_top30_futures: {e}")
        print(traceback.format_exc())
        return []


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
# Market sentiment (long/short %)
# =============================
async def get_market_sentiment():
    try:
        coins = await get_top30_futures(limit=30)
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
# Signal Generator V2 (theo trend, thoáng)
# =============================
async def analyze_coin_signal_v2(coin: dict, market_trend: str = "LONG") -> dict | None:
    symbol = coin["symbol"]
    last_price = coin["lastPrice"]
    change_pct = coin["change_pct"]

    closes = await fetch_klines(symbol, limit=100)
    if not closes or len(closes) < 30:
        return None

    # Indicators
    rsi = calculate_rsi(closes, 14)
    ma5, ma20 = np.mean(closes[-5:]), np.mean(closes[-20:])

    # Xác định hướng vào lệnh theo xu hướng thị trường
    side = market_trend
    if market_trend == "LONG" and change_pct < 0:
        return None
    if market_trend == "SHORT" and change_pct > 0:
        return None

    # ATR tính biên độ dao động
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

    # Strength thoáng (40–100)
    strength = 50
    if (side == "LONG" and rsi < 40) or (side == "SHORT" and rsi > 60):
        strength += 20
    if abs(change_pct) > 1:
        strength += 10

    strength = min(100, max(40, strength))  

    label = "⭐ Tín hiệu theo trend ⭐" if strength >= 60 else "Tín hiệu"

    return {
        "symbol": symbol,
        "direction": side,
        "orderType": "MARKET",
        "entry": round(entry_price, 4),
        "tp": round(tp_price, 4),
        "sl": round(sl_price, 4),
        "strength": strength,
        "reason": f"{label} | RSI={rsi:.1f} | MA5={ma5:.4f}, MA20={ma20:.4f} "
                  f"| Δ {change_pct:.2f}% | Trend={market_trend}"
    }


# =============================
# Lấy tỷ giá USDT/VND từ Binance
# =============================
async def get_usdt_vnd_rate() -> float:
    try:
        url = "https://api.binance.com/api/v3/ticker/price?symbol=USDTBUSD"
        url_vnd = "https://api.binance.com/api/v3/ticker/price?symbol=BUSDVND"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as r1, session.get(url_vnd, timeout=10) as r2:
                usdt_busd = float((await r1.json())["price"])
                busd_vnd = float((await r2.json())["price"])
                return usdt_busd * busd_vnd
    except Exception as e:
        print(f"[ERROR] get_usdt_vnd_rate: {e}")
        return 0.0
