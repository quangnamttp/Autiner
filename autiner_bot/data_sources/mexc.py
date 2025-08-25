import aiohttp
from typing import List, Dict, Any

MEXC_API = "https://contract.mexc.com"
HEADERS = {"Accept": "application/json"}

# =============================
# Utils
# =============================
async def _get_json(session: aiohttp.ClientSession, url: str, params: dict = None):
    async with session.get(
        url,
        params=params,
        headers=HEADERS,
        timeout=aiohttp.ClientTimeout(total=15)
    ) as r:
        r.raise_for_status()
        return await r.json()


# =============================
# Tỷ giá USDT/VND
# =============================
async def get_usdt_vnd_rate() -> float:
    """
    Lấy tỷ giá USDT/VND từ Binance P2P.
    """
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
# Fetch tickers (24h)
# =============================
async def fetch_24h_tickers(session: aiohttp.ClientSession) -> List[Dict[str, Any]]:
    """
    Trả về toàn bộ 24h tickers của Futures (MEXC).
    Lọc lấy các symbol kết thúc bằng '_USDT'.
    """
    url = f"{MEXC_API}/api/v1/contract/ticker"
    data = await _get_json(session, url)
    return [d for d in data.get("data", []) if d.get("symbol", "").endswith("_USDT")]


# =============================
# Top gainers
# =============================
async def top_gainers(session: aiohttp.ClientSession, n: int = 5) -> List[Dict[str, Any]]:
    t = await fetch_24h_tickers(session)
    t = sorted(t, key=lambda x: float(x.get("riseFallRate", 0) or 0), reverse=True)
    return t[:n]


# =============================
# Funding rate
# =============================
async def funding_rate_latest(session: aiohttp.ClientSession, symbol: str) -> float:
    url = f"{MEXC_API}/api/v1/contract/funding_rate/{symbol}"
    data = await _get_json(session, url)
    try:
        return float(data["data"]["rate"])
    except Exception:
        return 0.0


# =============================
# Klines
# =============================
async def klines(session: aiohttp.ClientSession, symbol: str, interval: str = "Min5", limit: int = 200):
    url = f"{MEXC_API}/api/v1/contract/kline/{symbol}"
    data = await _get_json(session, url, params={"interval": interval, "limit": limit})
    return data.get("data", [])


# =============================
# Indicators
# =============================
def rsi(series, period: int = 14) -> float:
    if len(series) <= period:
        return 50.0
    gains, losses = [], []
    for i in range(1, period + 1):
        delta = series[-i] - series[-i - 1]
        (gains if delta >= 0 else losses).append(abs(delta))
    avg_gain = sum(gains) / len(gains) if gains else 0.0
    avg_loss = sum(losses) / len(losses) if losses else 1e-9
    rs = (avg_gain / avg_loss) if avg_loss else 0
    return 100 - (100 / (1 + rs))


def ema(series, period: int):
    if len(series) < period:
        return series[-1]
    k = 2 / (period + 1)
    e = series[-period]
    for p in series[-period + 1:]:
        e = p * k + e * (1 - k)
    return e


# =============================
# Quick metrics cho 1 symbol
# =============================
async def quick_signal_metrics(session: aiohttp.ClientSession, symbol: str, interval: str = "Min5"):
    ks = await klines(session, symbol, interval=interval, limit=200)
    closes = [float(k[4]) for k in ks] if ks else []
    vol = [float(k[5]) for k in ks] if ks else []

    if not closes:
        return {"last": 0, "rsi": 50, "ema50": 0, "ema200": 0, "trend": 0, "vol_ratio": 1.0, "funding": 0.0}

    last = closes[-1]
    rsi_val = rsi(closes, 14)
    ema50 = ema(closes, 50)
    ema200 = ema(closes, 200 if len(closes) >= 200 else max(10, len(closes)-1))
    trend = 1 if ema50 > ema200 else -1

    if len(vol) >= 20:
        ma20 = sum(vol[-20:]) / 20.0
        vol_ratio = (vol[-1] / ma20) if ma20 > 1e-12 else 0.0
    else:
        vol_ratio = 1.0

    fund = await funding_rate_latest(session, symbol)
    return {
        "last": last,
        "rsi": rsi_val,
        "ema50": ema50,
        "ema200": ema200,
        "trend": trend,
        "vol_ratio": vol_ratio,
        "funding": fund,
    }


# =============================
# Active symbols (lọc volume)
# =============================
async def active_symbols(session: aiohttp.ClientSession, min_quote_volume: float = 5_000_000.0) -> List[str]:
    """
    Lấy danh sách toàn bộ Futures USDT có amount24 >= ngưỡng (mặc định 5 triệu USDT/24h).
    Trả về danh sách symbol, ví dụ ["BTC_USDT","ETH_USDT",...]
    """
    tickers = await fetch_24h_tickers(session)
    syms: List[str] = []
    for t in tickers:
        try:
            qv = float(t.get("amount24", 0) or 0)
            if qv >= min_quote_volume:
                syms.append(t["symbol"])
        except Exception:
            continue
    syms.sort()
    return syms
