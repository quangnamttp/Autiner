import aiohttp
import hmac, hashlib, time
import numpy as np

# =============================
# API Keys & Base URL
# =============================
MEXC_API_KEY = "mx0vgl8vcbqeQC9MYS"
MEXC_API_SECRET = "3974e94436b0453da81fdb0289be0b8c"
MEXC_BASE_URL = "https://contract.mexc.com"


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
            async with session.get(url, params=payload, headers=headers, timeout=10) as resp:
                text = await resp.text()
                if resp.status != 200:
                    print(f"[HTTP ERROR] {url} → {resp.status} | {text[:200]}")
                    return None
                return await resp.json()
    except Exception as e:
        print(f"[EXCEPTION] {url} → {e}")
        return None


# =============================
# Private API: ký request & account
# =============================
def sign_params(params: dict):
    query = "&".join([f"{k}={v}" for k, v in sorted(params.items())])
    signature = hmac.new(
        MEXC_API_SECRET.encode("utf-8"),
        query.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    params["signature"] = signature
    return params


async def mexc_private_request(endpoint: str, method="GET", params=None):
    if params is None:
        params = {}
    params["api_key"] = MEXC_API_KEY
    params["req_time"] = int(time.time() * 1000)
    signed_params = sign_params(params)
    headers = {"Content-Type": "application/json"}

    url = f"{MEXC_BASE_URL}{endpoint}"
    async with aiohttp.ClientSession() as session:
        if method == "GET":
            return await safe_get_json(url, session, method="GET", payload=signed_params, headers=headers)
        else:
            return await safe_get_json(url, session, method="POST", payload=signed_params, headers=headers)


async def get_account_info():
    """Lấy balance USDT Futures"""
    data = await mexc_private_request("/api/v1/private/account/assets", method="GET")
    if not data or "data" not in data:
        return None
    for asset in data["data"]:
        if asset.get("currency") == "USDT":
            return asset
    return None


# ==============================
# Chuẩn hóa symbol cho Futures
# ==============================
def normalize_symbol(symbol: str) -> str:
    if not symbol.endswith("_UMCBL"):
        return symbol.upper().replace("_USDT", "_USDT_UMCBL")
    return symbol.upper()


# =============================
# Public API: tỷ giá, sentiment, funding
# =============================
async def get_usdt_vnd_rate():
    """Lấy tỷ giá USDT/VND từ Binance P2P"""
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


async def get_market_sentiment():
    """Xu hướng Long/Short toàn thị trường"""
    try:
        url = f"{MEXC_BASE_URL}/api/v1/contract/future/ticker"
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


async def get_market_funding_volume():
    """Funding rate + volume toàn thị trường"""
    try:
        url = f"{MEXC_BASE_URL}/api/v1/contract/funding_rate"
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
# Top Futures
# =============================
async def get_top20_futures(limit: int = 20):
    """Top futures theo volume (lọc coin rác an toàn)"""
    try:
        url = f"{MEXC_BASE_URL}/api/v1/contract/future/ticker"
        async with aiohttp.ClientSession() as session:
            data = await safe_get_json(url, session)
            if not data:
                print("[ERROR] get_top20_futures: Không nhận được dữ liệu từ API")
                return []
            if not data.get("success") or "data" not in data:
                print(f"[ERROR] get_top20_futures: Response lỗi {data}")
                return []

            filtered = []
            for c in data["data"]:
                if not c["symbol"].endswith("_USDT"):
                    continue
                last_price = float(c.get("lastPrice", 0))
                volume = float(c.get("volume", 0))

                # Chỉ lọc coin rác giá cực thấp
                if last_price < 0.001:
                    continue

                filtered.append({
                    "symbol": c["symbol"],
                    "lastPrice": last_price,
                    "volume": volume,
                    "change_pct": float(c.get("riseFallRate", 0))
                })

            if not filtered:
                print("[WARNING] get_top20_futures: Không còn coin hợp lệ sau khi lọc")
                return []

            return sorted(filtered, key=lambda x: x["volume"], reverse=True)[:limit]

    except Exception as e:
        print(f"[EXCEPTION] get_top20_futures: {e}")
    return []


# =============================
# Indicator (RSI, MA)
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


async def fetch_klines(symbol: str, limit: int = 100):
    """Lấy dữ liệu Kline"""
    sym = normalize_symbol(symbol)
    url = f"{MEXC_BASE_URL}/api/v1/contract/kline/{sym}?interval=Min1&limit=120"
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
# Signal Generator V2
# =============================
async def analyze_coin_signal_v2(coin: dict) -> dict:
    """Phân tích tín hiệu: RSI + MA + Volume"""
    symbol = coin["symbol"]
    last_price = coin["lastPrice"]
    change_pct = coin["change_pct"]
    volume = coin.get("volume", 0)

    if last_price < 0.001:
        return {"symbol": symbol, "direction": "N/A", "entry": 0, "tp": 0, "sl": 0, "strength": 0, "reason": "⚠️ Coin rác <0.001"}

    closes = await fetch_klines(symbol, limit=100)
    if not closes or len(closes) < 20:
        return {"symbol": symbol, "direction": "N/A", "entry": 0, "tp": 0, "sl": 0, "strength": 0, "reason": "⚠️ Không đủ dữ liệu Kline"}

    rsi = calculate_rsi(closes, 14)
    ma5, ma20 = np.mean(closes[-5:]), np.mean(closes[-20:])
    trend = "LONG" if change_pct >= 0 and ma5 >= ma20 else "SHORT"
    side = trend

    # Ngược trend phải đủ RSI + MA đảo chiều + volume cực lớn
    if trend == "LONG" and rsi > 75 and ma5 < ma20 and volume >= 30_000_000:
        side = "SHORT"
    elif trend == "SHORT" and rsi < 25 and ma5 > ma20 and volume >= 30_000_000:
        side = "LONG"

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
    if volume > 10_000_000:
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
