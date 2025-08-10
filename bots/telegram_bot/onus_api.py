import time
import requests
from settings import ONUS_TIMEOUT, ONUS_RETRY, ONUS_CACHE_TTL, ONUS_MIN_REFRESH_SEC, ONUS_PROXY

ENDPOINTS = [
    "https://onus-relay.quangnamttp.workers.dev/overview",
    "https://goonus.io/api/v1/futures/market-overview",
    "https://api-gateway.onus.io/futures/api/v1/market/overview",
    "https://api.onus.io/futures/api/v1/market/overview",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/124 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://goonus.io/future",
    "Origin": "https://goonus.io",
    "Connection": "keep-alive",
}

_cache = {"ts": 0.0, "data": [], "live": False}

def _norm(item: dict) -> dict | None:
    ctype = (item.get("contractType") or item.get("type") or "").lower()
    if ctype and "perpetual" not in ctype:
        return None
    sym = item.get("symbol") or item.get("pair") or item.get("token")
    if not sym:
        return None

    def f(v, d=0.0):
        try: return float(v)
        except: return d

    price   = f(item.get("lastPriceVnd") or item.get("priceVnd") or item.get("lastPrice") or item.get("last"))
    vol_vnd = f(item.get("volumeValueVnd") or item.get("quoteVolumeVnd") or item.get("quoteVolume") or item.get("volume"))
    change  = f(item.get("priceChangePercent") or item.get("changePercent") or item.get("percentChange"))
    funding = f(item.get("fundingRate") or item.get("currentFundingRate") or item.get("funding"))
    return {
        "symbol": sym,
        "lastPrice": price,
        "volumeValueVnd": vol_vnd,
        "change24h_pct": change,
        "fundingRate": funding,
        "contractType": "perpetual",
    }

def _try_get(url: str):
    proxies = {"http": ONUS_PROXY, "https": ONUS_PROXY} if ONUS_PROXY else None
    for _ in range(max(1, ONUS_RETRY)):
        try:
            r = requests.get(url, headers=HEADERS, timeout=ONUS_TIMEOUT, proxies=proxies)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
    return None

def fetch_onus_futures_top30() -> list[dict]:
    now = time.time()
    # dùng cache nếu còn tươi
    if _cache["data"] and now - _cache["ts"] < ONUS_CACHE_TTL:
        return _cache["data"]

    # đảm bảo không refresh quá dày
    if _cache["data"] and now - _cache["ts"] < ONUS_MIN_REFRESH_SEC:
        return _cache["data"]

    for url in ENDPOINTS:
        raw = _try_get(url)
        if not raw:
            continue
        data = raw.get("data") if isinstance(raw, dict) else raw
        if not isinstance(data, list):
            continue

        out = []
        for it in data:
            norm = _norm(it)
            if norm:
                out.append(norm)
        if not out:
            continue

        out.sort(key=lambda d: d.get("volumeValueVnd", 0.0), reverse=True)
        top30 = out[:30]

        _cache["ts"] = now
        _cache["data"] = top30
        _cache["live"] = True
        return top30

    # không lấy được → dùng cache cũ (đánh dấu live=False)
    _cache["live"] = False
    return _cache["data"]

def cache_status():
    return {"live": _cache["live"], "age_sec": int(time.time() - _cache["ts"]) if _cache["ts"] else None}
