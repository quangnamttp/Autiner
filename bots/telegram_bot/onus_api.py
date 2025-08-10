import requests
import time

ONUS_FUTURES_URL = "https://goonus.io/api/v1/futures/market-overview"

_cache = {
    "timestamp": 0,
    "data": []
}

def fetch_onus_futures_top30():
    """
    Lấy Top 30 Futures từ ONUS theo Volume 24h (VND)
    Cache 60 giây để tránh gọi API liên tục
    """
    now = time.time()
    if now - _cache["timestamp"] < 60 and _cache["data"]:
        return _cache["data"]

    try:
        resp = requests.get(ONUS_FUTURES_URL, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        # Lọc hợp đồng Futures
        futures = [c for c in data if c.get("contractType") == "perpetual"]

        # Sắp xếp theo volume giảm dần
        futures.sort(key=lambda x: x.get("volumeValueVnd", 0), reverse=True)

        # Giữ Top 30
        top30 = futures[:30]

        _cache["timestamp"] = now
        _cache["data"] = top30
        return top30

    except Exception as e:
        print("[ONUS_API] Lỗi lấy dữ liệu:", e)
        return _cache["data"]  # trả về cache cũ nếu có
