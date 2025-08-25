import aiohttp
import numpy as np
import traceback

MEXC_BASE_URL = "https://contract.mexc.com"

# =============================
# Lấy dữ liệu ticker Futures (top coin)
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
# Lấy dữ liệu nến (kline)
# =============================
async def get_kline(symbol: str, interval: str = "Min1", limit: int = 100):
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
# EMA / RSI / MACD
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

def calc_macd(values, fast=12, slow=26, signal=9):
    if len(values) < slow:
        return 0, 0
    ema_fast = calc_ema(values, fast)
    ema_slow = calc_ema(values, slow)
    macd_val = ema_fast - ema_slow
    macd_signal = calc_ema(values, signal)
    return macd_val, macd_signal


# =============================
# PHÂN TÍCH XU HƯỚNG 1 COIN (SCORING, KHÔNG FALLBACK)
# =============================
async def analyze_coin_trend(symbol: str, interval="Min15", limit=50):
    try:
        klines = await get_kline(symbol, interval, limit)
        if not klines or len(klines) < 20:
            return {"side": None, "strength": 0, "reason": "No data", "is_weak": True}

        closes = [k["close"] for k in klines]
        last = closes[-1]

        ema6 = calc_ema(closes, 6)
        ema12 = calc_ema(closes, 12)
        rsi = calc_rsi(closes, 14)
        macd_val, macd_sig = calc_macd(closes)

        funding = await get_funding_rate(symbol)
        orderbook = await get_orderbook(symbol)

        # ---- Scoring ----
        score, reasons = 0, []
        side = "LONG" if ema6 > ema12 else "SHORT"

        # EMA cross
        score += 1; reasons.append(f"EMA6={ema6:.2f}, EMA12={ema12:.2f}")

        # RSI
        if side == "LONG" and rsi > 55:
            score += 1; reasons.append(f"RSI={rsi:.1f}>55")
        elif side == "SHORT" and rsi < 45:
            score += 1; reasons.append(f"RSI={rsi:.1f}<45")

        # MACD confirm
        if side == "LONG" and macd_val > macd_sig:
            score += 1; reasons.append("MACD xác nhận LONG")
        elif side == "SHORT" and macd_val < macd_sig:
            score += 1; reasons.append("MACD xác nhận SHORT")

        # Funding bias
        if side == "LONG" and funding >= 0:
            score += 1; reasons.append(f"Funding={funding:.4f} ≥ 0")
        elif side == "SHORT" and funding <= 0:
            score += 1; reasons.append(f"Funding={funding:.4f} ≤ 0")

        # Orderbook
        if orderbook:
            bids, asks = orderbook.get("bids", 1), orderbook.get("asks", 1)
            if side == "LONG" and bids > asks:
                score += 1; reasons.append("Orderbook BUY>SELL")
            elif side == "SHORT" and asks > bids:
                score += 1; reasons.append("Orderbook SELL>BUY")

        # Volume spike (nến cuối vs trung bình)
        avg_vol = np.mean([k["volume"] for k in klines[:-1]]) or 1
        last_vol = klines[-1]["volume"]
        if last_vol > 1.5 * avg_vol:
            score += 1; reasons.append(f"Vol spike x{last_vol/avg_vol:.2f}")

        # ---- Strength ----
        strength = (score / 6) * 100
        is_weak = strength < 70  # chỉ >=70% mới coi là mạnh

        return {
            "side": side,
            "strength": round(strength, 1),
            "reason": ", ".join(reasons),
            "is_weak": is_weak
        }
    except Exception as e:
        print(f"[ERROR] analyze_coin_trend({symbol}): {e}")
        return {"side": None, "strength": 0, "reason": "Error", "is_weak": True}
