import asyncio
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

# dùng lại nguồn đã chạy ổn ở onus_api.py
from bots.telegram_bot.onus_api import fetch_onus_futures_top30

_TOP = []
_REFRESH_EVERY = 300  # 5 phút

def _fmt_billion(v: float) -> str:
    try:
        v = float(v)
    except Exception:
        return "-"
    if v >= 1_000_000_000:
        return f"{v/1_000_000_000:.1f}B"
    if v >= 1_000_000:
        return f"{v/1_000_000:.1f}M"
    return f"{v:,.0f}"

async def _refresh_once():
    """Gọi hàm sync fetch_onus_futures_top30() trong thread để không block event loop."""
    try:
        data = await asyncio.to_thread(fetch_onus_futures_top30)
        # Lấy tối đa 20 coin cho gọn
        return data[:20] if data else []
    except Exception as e:
        print("[/top] refresh error:", e)
        return []

async def _updater_loop():
    global _TOP
    while True:
        new_top = await _refresh_once()
        if new_top:
            _TOP = new_top
        await asyncio.sleep(_REFRESH_EVERY)

async def cmd_top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Hiển thị TOP 20 Futures theo vol VND từ cache (nếu cache trống sẽ refresh nhanh 1 lần)."""
    global _TOP
    if not _TOP:
        await update.message.reply_text("⏳ Đang tải dữ liệu Onus…")
        _TOP = await _refresh_once()
        if not _TOP:
            await update.message.reply_text("⚠️ Hiện chưa lấy được dữ liệu. Thử lại sau nhé.")
            return

    lines = ["🏆 TOP 20 COIN VOLUME CAO (ONUS)\n"]
    for i, c in enumerate(_TOP, 1):
        sym = c.get("symbol", "-")
        price = c.get("lastPrice") or c.get("priceVnd") or 0
        vol_vnd = c.get("volumeValueVnd") or 0
        price_txt = f"{int(price):,}₫" if price else "-"
        vol_txt = _fmt_billion(vol_vnd)
        lines.append(f"{i:>2}. {sym:<8} {price_txt:<14} Vol:{vol_txt}")

    await update.message.reply_text("\n".join(lines))

def register_top_handler(app):
    app.add_handler(CommandHandler("top", cmd_top))

def start_top_updater():
    # chạy nền cập nhật cache mỗi 5 phút
    asyncio.get_event_loop().create_task(_updater_loop())
