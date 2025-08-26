import aiohttp
import numpy as np
import traceback

MEXC_BASE_URL = "https://contract.mexc.com"

# =============================
# Lấy dữ liệu ticker Futures
# =============================
async def get_top_futures(limit: int = 30):
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
        print(f"[ERROR] get_top_futures: {e}")
        print(traceback.format_exc())
        return []


# =============================
# Lấy tỷ giá USDT/VND
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
# EMA
# =============================
def calc_ema(values, period):
    if len(values) < period:
        return sum(values) / len(values)
    k = 2 / (period + 1)
    ema_val = values[0]
    for v in values[1:]:
        ema_val = v * k + ema_val * (1 - k)
    return ema_val


# =============================
# Kline
# =============================
async def get_kline(symbol: str, interval: str = "Min15", limit: int = 100):
    try:
        url = f"{MEXC_BASE_URL}/api/v1/contract/kline/{symbol}?interval={interval}&limit={limit}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                data = await resp.json()
                if not data or "data" not in data:
                    return []
                return [
                    {"time": k[0], "open": float(k[1]), "high": float(k[2]),
                     "low": float(k[3]), "close": float(k[4]), "volume": float(k[5])}
                    for k in data["data"]
                ]
    except Exception as e:
        print(f"[ERROR] get_kline({symbol}): {e}")
        return []


# =============================
# Phân tích xu hướng 1 coin (EMA6 / EMA12 / EMA20)
# =============================
async def analyze_coin_trend(symbol: str, interval="Min15", limit=100):
    try:
        klines = await get_kline(symbol, interval, limit)
        if not klines or len(klines) < 20:
            return None

        closes = [k["close"] for k in klines]
        last = closes[-1]

        ema6 = calc_ema(closes, 6)
        ema12 = calc_ema(closes, 12)
        ema20 = calc_ema(closes, 20)

        # Xu hướng chính
        if ema6 > ema12 > ema20:
            side = "LONG"
        elif ema6 < ema12 < ema20:
            side = "SHORT"
        else:
            side = "LONG" if ema6 > ema20 else "SHORT"

        # Strength dựa EMA6-EMA20
        diff = abs(ema6 - ema20) / last * 100
        strength = min(100, max(50, diff * 10))  # scale từ 50–100

        reason = f"EMA6={ema6:.3f}, EMA12={ema12:.3f}, EMA20={ema20:.3f}"

        return {
            "side": side,
            "strength": round(strength, 1),
            "reason": reason,
            "ema6": ema6,
            "ema12": ema12,
            "ema20": ema20,
            "is_weak": False  # không còn 'tham khảo'
        }
    except Exception as e:
        print(f"[ERROR] analyze_coin_trend({symbol}): {e}")
        return None
