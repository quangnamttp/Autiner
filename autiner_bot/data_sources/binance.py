import aiohttp
import traceback
import numpy as np

BINANCE_FUTURES_URL = "https://fapi.binance.com"
BINANCE_P2P_URL = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"

P2P_HEADERS = {
    "Content-Type": "application/json",
    "Origin": "https://p2p.binance.com",
    "Referer": "https://p2p.binance.com/",
    "User-Agent": "Mozilla/5.0"
}

# =============================
# Lấy toàn bộ coin Futures (24h ticker)
# =============================
async def get_all_futures():
    try:
        url = f"{BINANCE_FUTURES_URL}/fapi/v1/ticker/24hr"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=15) as resp:
                if resp.status != 200:
                    txt = await resp.text()
                    print(f"[ERROR] get_all_futures {resp.status}: {txt}")
                    return []
                data = await resp.json()
                return data if isinstance(data, list) else []
    except Exception as e:
        print(f"[ERROR] get_all_futures: {e}")
        print(traceback.format_exc())
        return []

# =============================
# Lấy tỷ giá USDT/VND (Binance P2P, SELL)
# =============================
async def get_usdt_vnd_rate() -> float:
    payload = {
        "asset": "USDT",
        "fiat": "VND",
        "merchantCheck": False,
        "page": 1,
        "rows": 10,
        "tradeType": "SELL",
        "payTypes": [],
        "publisherType": None
    }
    try:
        async with aiohttp.ClientSession(headers=P2P_HEADERS) as session:
            async with session.post(BINANCE_P2P_URL, json=payload, timeout=15) as resp:
                if resp.status != 200:
                    txt = await resp.text()
                    print(f"[ERROR] get_usdt_vnd_rate {resp.status}: {txt}")
                    return 0.0
                data = await resp.json()
                advs = data.get("data", [])
                prices = []
                for item in advs[:5]:
                    adv = item.get("adv") or {}
                    p = adv.get("price")
                    if p is not None:
                        try:
                            prices.append(float(p))
                        except:
                            pass
                return float(sum(prices) / len(prices)) if prices else 0.0
    except Exception as e:
        print(f"[ERROR] get_usdt_vnd_rate: {e}")
        print(traceback.format_exc())
        return 0.0

# =============================
# Lấy dữ liệu Kline (nến) Futures
# =============================
async def get_kline(symbol: str, interval="15m", limit=250):
    symbol = symbol.upper()
    try:
        url = f"{BINANCE_FUTURES_URL}/fapi/v1/klines?symbol={symbol}&interval={interval}&limit={limit}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=15) as resp:
                if resp.status != 200:
                    txt = await resp.text()
                    print(f"[ERROR] get_kline {symbol} {resp.status}: {txt}")
                    return []
                data = await resp.json()
                return data if isinstance(data, list) else []
    except Exception as e:
        print(f"[ERROR] get_kline({symbol}): {e}")
        print(traceback.format_exc())
        return []

# =============================
# Indicator helpers (EMA, RSI, MACD)
# =============================
def _ema(series, period):
    series = np.asarray(series, dtype=float)
    if len(series) < period:
        return float(series[-1])
    k = 2 / (period + 1)
    ema = series[0]
    for v in series[1:]:
        ema = v * k + ema * (1 - k)
    return float(ema)

def _ema_series(series, period):
    series = np.asarray(series, dtype=float)
    k = 2 / (period + 1)
    out = np.empty_like(series)
    out[0] = series[0]
    for i in range(1, len(series)):
        out[i] = series[i] * k + out[i-1] * (1 - k)
    return out

def _rsi_wilder(closes, period=14):
    closes = np.asarray(closes, dtype=float)
    if len(closes) < period + 1:
        return 50.0
    deltas = np.diff(closes)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])
    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calculate_indicators(klines):
    try:
        closes = np.array([float(k[4]) for k in klines], dtype=float)
        if len(closes) < 26:
            return {}
        ema20_val = _ema(closes, 20)
        ema50_val = _ema(closes, 50) if len(closes) >= 50 else closes[-1]
        sma20 = float(np.mean(closes[-20:])) if len(closes) >= 20 else closes[-1]
        std20 = float(np.std(closes[-20:])) if len(closes) >= 20 else 0.0
        upper = sma20 + 2 * std20
        lower = sma20 - 2 * std20
        last_close = float(closes[-1])
        if last_close >= upper:
            bb_status = "gần/đụng biên trên (cảnh giác điều chỉnh)"
        elif last_close <= lower:
            bb_status = "gần/đụng biên dưới (có thể hồi kỹ thuật)"
        else:
            bb_status = "trong dải (sideway)"
        rsi = round(_rsi_wilder(closes, 14), 2)
        ema12_series = _ema_series(closes, 12)
        ema26_series = _ema_series(closes, 26)
        macd_line = ema12_series - ema26_series
        signal_series = _ema_series(macd_line, 9)
        macd_now = float(macd_line[-1])
        signal_now = float(signal_series[-1])
        macd_signal = "bullish" if macd_now > signal_now else "bearish"
        return {
            "RSI": rsi,
            "MACD": macd_signal,
            "EMA20": round(ema20_val, 6),
            "EMA50": round(ema50_val, 6),
            "Bollinger": bb_status,
            "last_close": last_close,
        }
    except Exception as e:
        print(f"[ERROR] calculate_indicators: {e}")
        print(traceback.format_exc())
        return {}

# =============================
# Phân tích coin
# =============================
async def analyze_coin(symbol: str):
    try:
        symbol = symbol.upper()
        if not symbol.endswith("USDT"):
            symbol += "USDT"
        klines = await get_kline(symbol, "15m", 250)
        indicators = calculate_indicators(klines) if klines else {}
        if not indicators:
            return {"side": "LONG", "strength": 50, "reason": "Không đủ dữ liệu (nến < 26)"}
        rsi, macd = indicators["RSI"], indicators["MACD"]
        ema20, ema50 = indicators["EMA20"], indicators["EMA50"]
        score = 0
        reasons = []
        # RSI
        if rsi < 30:
            score += 3; reasons.append("RSI < 30 (quá bán)")
        elif 30 <= rsi <= 45:
            score += 1; reasons.append("RSI trung tính hơi yếu → tiềm năng hồi")
        elif rsi > 70:
            score -= 3; reasons.append("RSI > 70 (quá mua)")
        elif 55 <= rsi <= 70:
            score -= 1; reasons.append("RSI trung tính hơi mạnh → dễ điều chỉnh")
        # MACD
        if macd == "bullish":
            score += 2; reasons.append("MACD bullish (MACD > signal)")
        else:
            score -= 2; reasons.append("MACD bearish (MACD < signal)")
        # EMA cross
        if ema20 > ema50:
            score += 2; reasons.append("EMA20 > EMA50 (xu hướng tăng ngắn hạn)")
        else:
            score -= 2; reasons.append("EMA20 < EMA50 (xu hướng giảm ngắn hạn)")
        # Bollinger
        reasons.append(f"Bollinger: {indicators['Bollinger']}")
        side = "LONG" if score >= 0 else "SHORT"
        strength = max(10, min(90, 50 + score * 5))
        return {
            "side": side,
            "strength": int(strength),
            "reason": "; ".join(reasons),
            "last_close": indicators["last_close"],
        }
    except Exception as e:
        print(f"[ERROR] analyze_coin({symbol}): {e}")
        print(traceback.format_exc())
        return {"side": "LONG", "strength": 50, "reason": "Lỗi phân tích"}
