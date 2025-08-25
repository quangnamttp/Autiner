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
    except Exception:
        return 0


# =============================
# EMA / RSI
# =============================
def calc_ema(values, period):
    if len(values) < period:
        return sum(values) / len(values)
    k = 2 / (period + 1)
    ema_val = values[0]
    for v in values[1:]:
        ema_val = v * k + ema_val * (1 - k)
    return ema_val

def calc_rsi(closes, period=14):
    if len(closes) < period + 1:
        return 50
    deltas = np.diff(closes)
    ups = deltas[deltas > 0].sum() / period
    downs = -deltas[deltas < 0].sum() / period
    rs = ups / downs if downs != 0 else 0
    return 100 - (100 / (1 + rs))


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
    except Exception:
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
    except Exception:
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
    except Exception:
        return {}


# =============================
# Phân tích xu hướng 1 coin
# =============================
async def analyze_coin_trend(symbol: str, interval="Min5", limit=200):
    try:
        klines = await get_kline(symbol, interval, limit)
        if not klines or len(klines) < 50:
            return None

        closes = [k["close"] for k in klines]
        last = closes[-1]

        ema9 = calc_ema(closes, 9)
        ema21 = calc_ema(closes, 21)
        rsi = calc_rsi(closes, 14)

        funding = await get_funding_rate(symbol)
        orderbook = await get_orderbook(symbol)

        # Strength = độ chênh EMA
        diff = abs(ema9 - ema21) / last * 100
        strength = round(diff, 1)

        side = "LONG" if ema9 > ema21 else "SHORT"

        reasons = [
            f"Funding={funding:.4f}",
            f"RSI={rsi:.1f}",
            f"EMA9={ema9:.3f}, EMA21={ema21:.3f}"
        ]

        if orderbook:
            reasons.append(
                "Orderbook BUY>SELL" if orderbook.get("bids", 0) > orderbook.get("asks", 0)
                else "Orderbook SELL>BUY"
            )

        return {
            "side": side,
            "strength": strength,
            "reason": ", ".join(reasons),
            "ema9": ema9,
            "ema21": ema21,
            "rsi": rsi,
            "funding": funding,
            "orderbook": orderbook,
            "is_weak": strength < 50
        }
    except Exception as e:
        print(f"[ERROR] analyze_coin_trend({symbol}): {e}")
        return None
