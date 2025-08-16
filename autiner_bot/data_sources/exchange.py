import aiohttp
from autiner_bot.settings import S

# =============================
# Lấy tỷ giá USDT/VND từ MEXC
# =============================
async def get_usdt_vnd_rate() -> float | None:
    """
    Lấy tỷ giá USDT/VND trực tiếp từ API MEXC.
    Trả về float nếu thành công, None nếu thất bại.
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(S.MEXC_TICKER_VNDC_URL, timeout=10) as resp:
                data = await resp.json()
                if data.get("data"):
                    return float(data["data"][0]["last"])
    except Exception as e:
        print(f"[ERROR] get_usdt_vnd_rate: {e}")
    return None
