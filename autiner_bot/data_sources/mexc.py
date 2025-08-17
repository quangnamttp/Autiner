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
# Sentiment thị trường BTC
# =============================
async def get_market_sentiment():
    try:
        url = "https://contract.mexc.com/api/v1/contract/long_short_account_ratio?symbol=BTC_USDT&period=5m"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                data = await resp.json()
                if data.get("success") and data.get("data"):
                    latest = data["data"][-1]
                    return {
                        "long": float(latest.get("longAccount", 0)),
                        "short": float(latest.get("shortAccount", 0))
                    }
    except Exception as e:
        print(f"[ERROR] get_market_sentiment: {e}")
    return {"long": 0.0, "short": 0.0}


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
                        "funding": f"{float(latest.get('fundingRate', 0))*100:.4f}%",
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
    """
    Lấy danh sách top coin Futures USDT có volume cao nhất trên MEXC.
    """
    try:
        url = S.MEXC_TICKER_URL
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                data = await resp.json()
                if data.get("success") and "data" in data:
                    coins = data["data"]

                    # Lọc USDT pair
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

                    # Sort theo volume lớn nhất
                    sorted_coins = sorted(filtered, key=lambda x: x["volume"], reverse=True)
                    return sorted_coins[:limit]
    except Exception as e:
        print(f"[ERROR] get_top20_futures: {e}")

    return []


# =============================
# Detect trend (gộp từ trend_detector.py)
# =============================
async def detect_trend(limit: int = 5):
    """
    Trả về danh sách coin để bot dùng phân tích tín hiệu.
    - Lấy top 20 futures volume cao nhất
    - Chọn ra limit coin (vd: 5) có biến động mạnh nhất
    """
    try:
        coins = await get_top20_futures(limit=20)
        if not coins:
            return []

        # Ưu tiên chọn biến động mạnh nhất trong top 20
        sorted_by_change = sorted(coins, key=lambda x: abs(x["change_pct"]), reverse=True)

        return sorted_by_change[:limit]

    except Exception as e:
        print(f"[ERROR] detect_trend: {e}")
        return []


# =============================
# Tính RSI
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
    rsi = 100 - (100 / (1 + rs))
    return float(rsi)


# =============================
# Lấy dữ liệu Kline MEXC
# =============================
async def fetch_klines(symbol: str, limit: int = 100):
    """
    Lấy dữ liệu nến 1 phút từ MEXC.
    Trả về danh sách giá đóng cửa.
    """
    url = S.MEXC_KLINES_URL.format(sym=symbol)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                data = await resp.json()
                if data.get("success") and "data" in data:
                    closes = [float(c[4]) for c in data["data"]]  # c[4] = close price
                    return closes[-limit:]
    except Exception as e:
        print(f"[ERROR] fetch_klines {symbol}: {e}")
    return []


# =============================
# Phân tích tín hiệu nâng cấp
# =============================
async def analyze_coin_signal(coin: dict) -> dict:
    """
    Phân tích kỹ thuật:
    - RSI (14 kỳ, dữ liệu thực)
    - MA5, MA20
    - Entry linh hoạt (Market/Limit)
    - TP/SL động theo biến động
    """
    symbol = coin["symbol"]
    last_price = coin["lastPrice"]
    change_pct = coin["change_pct"]

    # --- Lấy dữ liệu nến ---
    closes = await fetch_klines(symbol, limit=50)
    if not closes:
        closes = [last_price] * 20  # fallback nếu API lỗi

    # --- RSI ---
    rsi = calculate_rsi(closes, 14)
    if rsi > 70:
        rsi_signal = "QUÁ MUA (SELL)"
    elif rsi < 30:
        rsi_signal = "QUÁ BÁN (BUY)"
    else:
        rsi_signal = "TRUNG LẬP"

    # --- MA ---
    ma5 = np.mean(closes[-5:]) if len(closes) >= 5 else last_price
    ma20 = np.mean(closes[-20:]) if len(closes) >= 20 else last_price
    ma_signal = "BUY" if ma5 > ma20 else "SELL"

    # --- Xác định hướng ---
    if rsi < 30 or (ma5 > ma20 and change_pct > 0):
        side = "LONG"
    elif rsi > 70 or (ma5 < ma20 and change_pct < 0):
        side = "SHORT"
    else:
        side = "LONG" if change_pct >= 0 else "SHORT"

    # --- Order type & Entry ---
    if abs(change_pct) > 2:  # biến động mạnh -> Market
        order_type = "MARKET"
        entry_price = last_price
    else:  # biến động vừa/nhỏ -> Limit
        order_type = "LIMIT"
        if side == "LONG":
            entry_price = min(last_price, ma5)  # mua rẻ hơn ở MA5
        else:  # SHORT
            entry_price = max(last_price, ma5)  # bán cao hơn ở MA5

    # --- TP/SL động ---
    base_volatility = max(1.0, abs(change_pct))
    tp_pct = base_volatility * 1.0
    sl_pct = 0.5

    if side == "SHORT":
        tp_pct = -tp_pct  # TP âm cho lệnh SHORT

    tp_price = entry_price * (1 + tp_pct / 100)
    sl_price = entry_price * (1 + sl_pct / 100)

    # --- Strength ---
    strength = min(100, max(1, int(abs(change_pct) * 10)))
    if side == "LONG" and rsi < 25:
        strength = min(100, strength + 30)
    if side == "SHORT" and rsi > 75:
        strength = min(100, strength + 30)

    return {
        "symbol": symbol,
        "direction": side,
        "orderType": order_type,
        "entry": entry_price,
        "tp": tp_price,
        "sl": sl_price,
        "tp_pct": tp_pct,
        "sl_pct": sl_pct,
        "strength": strength,
        "reason": f"RSI {rsi_signal} ({rsi:.1f}) | MA {ma_signal} "
                  f"(MA5={ma5:.4f}, MA20={ma20:.4f}) | Biến động {change_pct:.2f}%"
    }
