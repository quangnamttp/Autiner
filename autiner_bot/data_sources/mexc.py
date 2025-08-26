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
# EMA helper
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
async def get_kline(symbol: str, interval: str = "Min5", limit: int = 200):
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
# Funding Rate
# =============================
async def get_funding_rate(symbol: str) -> float:
    try:
        url = f"{MEXC_BASE_URL}/api/v1/contract/funding_rate/{symbol}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                if resp.status != 200:
                    return 0
                data = await resp.json()
                if not data or "data" not in data:
                    return 0
                return float(data["data"].get("rate", 0))
    except Exception as e:
        print(f"[ERROR] get_funding_rate({symbol}): {e}")
        return 0


# =============================
# Orderbook
# =============================
async def get_orderbook(symbol: str, depth: int = 20) -> dict:
    try:
        url = f"{MEXC_BASE_URL}/api/v1/contract/depth/{symbol}?limit={depth}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                if resp.status != 200:
                    return {}
                data = await resp.json()
                if not data or "data" not in data:
                    return {}
                bids = sum(float(b[1]) for b in data["data"].get("bids", []))
                asks = sum(float(a[1]) for a in data["data"].get("asks", []))
                return {"bids": bids, "asks": asks}
    except Exception as e:
        print(f"[ERROR] get_orderbook({symbol}): {e}")
        return {}


# =============================
# Phân tích xu hướng 1 coin (EMA6-EMA12-EMA20)
# =============================
async def analyze_coin_trend(symbol: str, interval="Min15", limit=100):
    try:
        klines = await get_kline(symbol, interval, limit)
        if not klines or len(klines) < 30:
            return {
                "side": "LONG",
                "strength": 10,
                "reason": "Không đủ dữ liệu",
                "is_weak": True
            }

        closes = [k["close"] for k in klines]
        last = closes[-1]

        ema6 = calc_ema(closes, 6)
        ema12 = calc_ema(closes, 12)
        ema20 = calc_ema(closes, 20)

        # logic xu hướng
        if ema6 > ema12 > ema20:
            side = "LONG"
            strength = 70
            reason = f"EMA6={ema6:.3f} > EMA12={ema12:.3f} > EMA20={ema20:.3f} (Tăng rõ)"
        elif ema6 < ema12 < ema20:
            side = "SHORT"
            strength = 70
            reason = f"EMA6={ema6:.3f} < EMA12={ema12:.3f} < EMA20={ema20:.3f} (Giảm rõ)"
        else:
            side = "LONG"
            strength = 30
            reason = f"EMA lộn xộn → Sideway ({ema6:.3f}, {ema12:.3f}, {ema20:.3f})"

        return {
            "side": side,
            "strength": strength,
            "reason": reason,
            "ema6": ema6,
            "ema12": ema12,
            "ema20": ema20,
            "is_weak": strength < 50
        }
    except Exception as e:
        print(f"[ERROR] analyze_coin_trend({symbol}): {e}")
        return {
            "side": "LONG",
            "strength": 10,
            "reason": "Error",
            "is_weak": True
        }


# =============================
# Phân tích xu hướng thị trường (Daily)
# =============================
async def analyze_market_trend():
    try:
        coins = await get_top_futures(limit=15)
        if not coins:
            return {"long": 50.0, "short": 50.0, "trend": "❓ Không xác định", "top": []}

        long_vol = sum(c["volume"] for c in coins if c["change_pct"] > 0)
        short_vol = sum(c["volume"] for c in coins if c["change_pct"] < 0)
        total_vol = long_vol + short_vol

        if total_vol == 0:
            long_pct, short_pct = 50.0, 50.0
        else:
            long_pct = round(long_vol / total_vol * 100, 1)
            short_pct = round(short_vol / total_vol * 100, 1)

        if long_pct > short_pct + 5:
            trend = "📈 Xu hướng TĂNG (phe LONG chiếm ưu thế)"
        elif short_pct > long_pct + 5:
            trend = "📉 Xu hướng GIẢM (phe SHORT chiếm ưu thế)"
        else:
            trend = "⚖️ Thị trường sideway"

        top = sorted(coins, key=lambda x: abs(x.get("change_pct", 0)), reverse=True)[:5]

        return {"long": long_pct, "short": short_pct, "trend": trend, "top": top}
    except Exception as e:
        print(f"[ERROR] analyze_market_trend: {e}")
        return {"long": 50.0, "short": 50.0, "trend": "❓ Không xác định", "top": []}
