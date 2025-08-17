from autiner_bot.data_sources.mexc import get_top20_futures

# =============================
# Lấy top coin để phân tích
# =============================
async def detect_trend(limit: int = 5):
    """
    Trả về danh sách coin để bot dùng phân tích tín hiệu.
    - Lấy top 20 futures volume cao nhất
    - Chọn ra limit coin (vd: 5) để gửi tín hiệu
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
