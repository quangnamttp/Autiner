import asyncio
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
from bots.telegram_bot.onus_api import fetch_onus_futures_top30, cache_status

_CACHE = []
_REFRESH_SEC = 300  # 5 phút

def _fmt_b(v: float) -> str:
    try: v=float(v)
    except: return "-"
    if v>=1_000_000_000: return f"{v/1_000_000_000:.1f}B"
    if v>=1_000_000: return f"{v/1_000_000:.1f}M"
    return f"{v:,.0f}"

async def _refresh_once():
    data = await asyncio.to_thread(fetch_onus_futures_top30)  # không block event loop
    return data[:20] if data else []

async def _loop():
    global _CACHE
    while True:
        data = await _refresh_once()
        if data: _CACHE = data
        await asyncio.sleep(_REFRESH_SEC)

async def cmd_top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global _CACHE
    if not _CACHE:
        await update.message.reply_text("⏳ Đang tải dữ liệu Onus…")
        _CACHE = await _refresh_once()
        if not _CACHE:
            await update.message.reply_text("⚠️ Onus không phản hồi. Đợi chút rồi /top lại nhé.")
            return

    st = cache_status()
    badge = "LIVE ✅" if st.get("live") else f"CACHE ⏱{st.get('age_sec')}s"
    lines = [f"🏆 TOP 20 COIN VOLUME CAO (ONUS) — {badge}\n"]
    for i, c in enumerate(_CACHE, 1):
        sym = c["symbol"]
        price = int(c["lastPrice"]) if c["lastPrice"] else 0
        vol = _fmt_b(c["volumeValueVnd"])
        chg = c.get("change24h_pct", 0.0)
        arrow = "🟢" if chg >= 0 else "🔴"
        lines.append(f"{i:>2}. {sym:<7} {price:,}₫  Vol:{vol:<6} {arrow} {chg:+.2f}%")
    await update.message.reply_text("\n".join(lines))

def register_top_handler(app):
    app.add_handler(CommandHandler("top", cmd_top))

def start_top_updater():
    asyncio.get_event_loop().create_task(_loop())
