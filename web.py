# --- THÊM IMPORT ---
import httpx
from fastapi.responses import JSONResponse
from urllib.parse import urlparse

# --- THAY MỚI KHỐI RELAY ONUS (DESKTOP) ---
ONUS_UPSTREAMS = [
    "https://goonus.io/api/v1/futures/market-overview",
    "https://api-gateway.onus.io/futures/api/v1/market/overview",
    "https://api.onus.io/futures/api/v1/market/overview",
]

def build_pc_headers(url: str) -> dict:
    host = urlparse(url).hostname or "goonus.io"
    origin = f"https://{host}"
    referer = "https://goonus.io/future" if host == "goonus.io" else origin
    return {
        "Host": host,
        "Connection": "keep-alive",
        # desktop only
        "sec-ch-ua": '"Not/A)Brand";v="99", "Google Chrome";v="124", "Chromium";v="124"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "Upgrade-Insecure-Requests": "1",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
        "Referer": referer,
        "Origin": origin,
        "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
        "Pragma": "no-cache",
        "Cache-Control": "no-cache",
    }

@app.get("/relay/onus")
async def relay_onus():
    """Proxy ONUS với header desktop (Windows + Chrome)."""
    async with httpx.AsyncClient(timeout=8, follow_redirects=True) as client:
        for u in ONUS_UPSTREAMS:
            try:
                r = await client.get(u, headers=build_pc_headers(u))
                if r.status_code == 200:
                    try:
                        data = r.json()
                    except Exception:
                        continue
                    arr = data if isinstance(data, list) else data.get("data", data)
                    if isinstance(arr, list):
                        return JSONResponse(arr)
                    return JSONResponse(data)
            except Exception:
                pass
    return JSONResponse({"ok": False, "error": "ONUS upstream unreachable"}, status_code=502)
