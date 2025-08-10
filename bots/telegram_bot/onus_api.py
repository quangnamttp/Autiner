import time
import requests

# Thứ tự ưu tiên các endpoint ONUS (họ hay đổi gateway)
ENDPOINTS = [
    "https://goonus.io/api/v1/futures/market-overview",
    "https://api-gateway.onus.io/futures/api/v1/market/overview",
    "https://api.onus.io/futures/api/v1/market/overview",
]

# Cache 60 giây để tránh gọi dồn dập
_cache = {"ts": 0.0, "data": []}
_CACHE_TTL = 60


def _normalize_item(x: dict) -> dict | None:
    """Chuẩn hóa 1 dòng dữ liệu futures từ ONUS về cùng format dùng trong bot."""
    # Chỉ lấy hợp đồng vĩnh cửu (perpetual)
    ctype = (x.get("contractType") or x.get("type") or "").lower()
    if ctype and "perpetual" not in ctype:
        return None

    symbol = x.get("symbol") or x.get("pair") or x.get("token") or ""
    if not symbol:
        return None

    # Giá VND (nhiều tên field khác nhau)
    price = (
        x.get("lastPriceVnd")
        or x.get("priceVnd")
        or x.get("lastPrice")
        or x.get("last")
        or 0
    )

    # Volume VND 24h (ưu tiên field theo VND)
    vol_vnd = (
        x.get("volumeValueVnd")
        or x.get("quoteVolumeVnd")
        or x.get("quoteVolume")  # đôi lúc đã là VND
        or x.get("volume")
        or 0
    )

    # % thay đổi 24h nếu có
    change_pct = (
        x.get("priceChangePercent")
        or x.get("changePercent")
        or x.get("percentChange")
        or 0
    )

    # Funding hiện tại nếu có
    funding = (
        x.get("fundingRate")
        or x.get("currentFundingRate")
        or x.get("funding")
        or 0
    )

    try:
        price = float(price)
    except Exception:
        price = 0.0
    try:
        vol_vnd = float(vol_vnd)
    except Exception:
        vol_vnd = 0.0
    try:
        change_pct = float(change_pct)
    except Exception:
        change_pct = 0.0
    try:
        funding = float(funding)
    except Exception:
        funding = 0.0

    return {
        "symbol": symbol,
        "lastPrice": price,            # VND (nếu nguồn đã quy đổi) hoặc giá trị số gần nhất
        "volumeValueVnd": vol_vnd,     # Volume quy về VND (ưu tiên)
        "change24h_pct": change_pct,   # %
        "fundingRate": funding,        # %
        "contractType": "perpetual",
    }


def fetch_onus_futures_top30() -> list[dict]:
    """
    Lấy Top 30 hợp đồng futures ONUS theo volume VND 24h.
    Trả về danh sách dict đã chuẩn hóa:
      [{symbol, lastPrice, volumeValueVnd, change24h_pct, fundingRate, contractType}]
    """
    now = time.time()
    if _cache["data"] and now - _cache["ts"] < _CACHE_TTL:
        return _cache["data"]

    for url in ENDPOINTS:
        try:
            r = requests.get(url, timeout=8)
            r.raise_for_status()
            raw = r.json()
            data = raw.get("data") if isinstance(raw, dict) else raw
            if not isinstance(data, list):
                continue

            out = []
            for item in data:
                norm = _normalize_item(item)
                if norm:
                    out.append(norm)

            if not out:
                continue

            # Sắp xếp theo volume giảm dần, lấy Top 30
            out.sort(key=lambda d: d.get("volumeValueVnd", 0.0), reverse=True)
            top30 = out[:30]

            # Lưu cache và trả về
            _cache["ts"] = now
            _cache["data"] = top30
            return top30

        except Exception:
            # thử endpoint tiếp theo
            continue

    # Nếu tất cả endpoint lỗi, trả cache cũ (nếu có), nếu không có thì list rỗng
    return _cache["data"]
