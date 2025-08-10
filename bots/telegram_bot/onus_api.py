import time
import requests

# Các endpoint ONUS (thử lần lượt)
ENDPOINTS = [
    "https://goonus.io/api/v1/futures/market-overview",
    "https://api-gateway.onus.io/futures/api/v1/market/overview",
    "https://api.onus.io/futures/api/v1/market/overview",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://goonus.io/future",
    "Origin": "https://goonus.io",
    "Connection": "keep-alive",
}

_cache = {"ts": 0.0, "data": []}
TTL = 60


def _norm(item: dict) -> dict | None:
    ctype = (item.get("contractType") or item.get("type") or "").lower()
    # chỉ lấy perpetual
    if ctype and "perpetual" not in ctype:
        return None

    sym = item.get("symbol") or item.get("pair") or item.get("token")
    if not sym:
        return None

    def f(v, default=0.0):
        try:
            return float(v)
        except Exception:
            return default

    price = f(item.get("lastPriceVnd") or item.get("priceVnd") or item.get("lastPrice") or item.get("last"))
    vol_vnd = f(item.get("volumeValueVnd") or item.get("quoteVolumeVnd") or item.get("quoteVolume") or item.get("volume"))
    change = f(item.get("priceChangePercent") or item.get("changePercent") or item.get("percentChange"))
    funding = f(item.get("fundingRate") or item.get("currentFundingRate") or item.get("funding"))

    return {
        "symbol": sym,
        "lastPrice": price,
        "volumeValueVnd": vol_vnd,
        "change24h_pct": change,
        "fundingRate": funding,
        "contractType": "perpetual",
    }


def fetch_onus_futures_top30() -> list[dict]:
    now = time.time()
    if _cache["data"] and now - _cache["ts"] < TTL:
        return _cache["data"]

    for url in ENDPOINTS:
        for attempt in range(2):  # retry nhẹ
            try:
                r = requests.get(url, headers=HEADERS, timeout=8)
                if r.status_code != 200:
                    continue
                raw = r.json()
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

                # sort theo vol VND
                out.sort(key=lambda d: d.get("volumeValueVnd", 0.0), reverse=True)
                top30 = out[:30]

                _cache["ts"] = now
                _cache["data"] = top30
                return top30
            except Exception:
                continue

    return _cache["data"]  # có thể rỗng nếu bị chặn hoàn toàn
