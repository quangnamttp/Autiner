import pytz
from datetime import datetime, time as dt_time, timedelta
from telegram import Update, ReplyKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application, ApplicationBuilder, CommandHandler,
    ContextTypes, MessageHandler, filters
)

from settings import (
    TELEGRAM_BOT_TOKEN, ALLOWED_USER_ID, TZ_NAME, DEFAULT_UNIT,
    SLOT_TIMES, NUM_SCALPING
)
from .mexc_api import top_symbols, pick_scalping_signals, fmt_vnd_price, fmt_usd_price

VN_TZ = pytz.timezone(TZ_NAME)
_current_unit = DEFAULT_UNIT  # "VND" | "USD"

# ====== Buttons & menu ======
BTN_STATUS   = "🔎 Trạng thái"
BTN_TOP      = "🏆 TOP 30 COIN"
BTN_TODAY    = "📅 Hôm nay"
BTN_TOMORROW = "📅 Ngày mai"
BTN_WEEK     = "📅 Cả tuần"
BTN_TEST     = "🧪 Test"
BTN_VND      = "💰 MEXC VND"
BTN_USD      = "💵 MEXC USD"

def main_menu_kb() -> ReplyKeyboardMarkup:
    # Hàng 1: 🔎 Trạng thái | TOP 30 COIN
    # Hàng 2: 📅 Hôm nay | 📅 Ngày mai
    # Hàng 3: 📅 Cả tuần | 🧪 Test
    # Hàng 4: 💰 MEXC VND | 💵 MEXC USD
    keyboard = [
        [BTN_STATUS, BTN_TOP],
        [BTN_TODAY, BTN_TOMORROW],
        [BTN_WEEK, BTN_TEST],
        [BTN_VND, BTN_USD],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ====== Helpers ======
def guard(update: Update) -> bool:
    return not (ALLOWED_USER_ID and update.effective_user and update.effective_user.id != ALLOWED_USER_ID)

def vn_now_str():
    now = datetime.now(VN_TZ)
    return now.strftime("%H:%M %d/%m/%Y")

def next_slot_info(now: datetime) -> tuple[str, int]:
    today = now.date()
    slots = []
    for hhmm in SLOT_TIMES:
        h, m = map(int, hhmm.split(":"))
        slots.append(VN_TZ.localize(datetime.combine(today, dt_time(h, m))))
    future = [s for s in slots if s > now]
    if future:
        nxt = future[0]
    else:
        h, m = map(int, SLOT_TIMES[0].split(":"))
        nxt = VN_TZ.localize(datetime.combine(today + timedelta(days=1), dt_time(h, m)))
    mins = max(0, int((nxt - now).total_seconds() // 60))
    return nxt.strftime("%H:%M"), mins

# ---------- TOP 30: chỉ coin + giá, căn thẳng cột ----------
def _price_for(c: dict, unit: str) -> str:
    if unit == "VND":
        return fmt_vnd_price(c["lastPriceVND"])
    else:
        return fmt_usd_price(c["lastPrice"])

def _render_top_table(coins: list[dict], unit: str) -> str:
    rows = []
    max_price_len = 0
    for c in coins:
        sym = c["symbol"].replace("_USDT", "")
        price = _price_for(c, unit)
        chg = float(c.get("change24h_pct", 0.0))
        arrow = "🟢" if chg > 0 else ("🔴" if chg < 0 else "⚪")
        rows.append((sym, price, arrow))
        max_price_len = max(max_price_len, len(price))

    lines = [f"📊 TOP 30 Futures (MEXC) — Đơn vị: {unit}", ""]
    for sym, price, arrow in rows:
        sym_fixed = f"{sym:<6}"[:6]   # [ SYM  ]
        pad = " " * (max_price_len - len(price))
        lines.append(f"<code>[ {sym_fixed} ]  {arrow} {pad}{price}</code>")
    return "\n".join(lines)

# ---------------- Commands ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not guard(update): 
        return
    await update.effective_chat.send_message(
        "📋 Menu điều khiển — chọn chức năng bên dưới:",
        reply_markup=main_menu_kb()
    )

async def top_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not guard(update): return
    coins, live, _ = top_symbols(unit=_current_unit, topn=30)
    if not live or not coins:
        await update.effective_chat.send_message("⚠️ Hiện không có dữ liệu. Thử lại sau nhé.")
        return
    text = _render_top_table(coins, _current_unit)
    await update.effective_chat.send_message(text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)

async def set_usd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global _current_unit
    if not guard(update): return
    _current_unit = "USD"
    await update.effective_chat.send_message("✅ Đã chuyển đơn vị hiển thị sang **USD**.", parse_mode=ParseMode.MARKDOWN)

async def set_vnd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global _current_unit
    if not guard(update): return
    _current_unit = "VND"
    await update.effective_chat.send_message("✅ Đã chuyển đơn vị hiển thị sang **VND**.", parse_mode=ParseMode.MARKDOWN)

# ------------- Gửi tín hiệu theo slot -------------
async def send_batch_scalping(context: ContextTypes.DEFAULT_TYPE):
    chat_id = ALLOWED_USER_ID
    signals, highlights, live, _ = pick_scalping_signals(_current_unit, NUM_SCALPING)

    if (not live) or (not signals):
        now = datetime.now(VN_TZ)
        nxt_hhmm, mins = next_slot_info(now)
        await context.bot.send_message(
            chat_id,
            f"⚠️ Slot {now.strftime('%H:%M')} không có tín hiệu.\n"
            f"↪️ Dự kiến slot tiếp theo: **{nxt_hhmm}** ({mins} phút nữa)."
        )
        return

    header = f"📌 Tín hiệu {NUM_SCALPING} lệnh (Scalping) — {vn_now_str()}"
    if highlights:
        header += "\n⭐ Nổi bật: " + " | ".join(highlights[:3])
    await context.bot.send_message(chat_id, header)

    for s in signals:
        msg = (
            f"📈 {s['token']} ({s['unit']}) — {'🟩' if s['side']=='LONG' else '🟥'} {s['side']}\n\n"
            f"🟢 Loại lệnh: {s['type']}\n"
            f"🔹 Kiểu vào lệnh: {s['orderType']}\n"
            f"💰 Entry: {s['entry']}\n"
            f"🎯 TP: {s['tp']}\n"
            f"🛡️ SL: {s['sl']}\n"
            f"📊 Độ mạnh: {s['strength']}%\n"
            f"📌 Lý do: {s['reason']}\n"
            f"🕒 Thời gian: {vn_now_str()}"
        )
        await context.bot.send_message(chat_id, msg)

# ------------- Router cho menu -------------
async def on_menu_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global _current_unit
    if not guard(update) or not update.message:
        return
    text = (update.message.text or "").strip()

    if text == BTN_STATUS:
        _, live, _ = top_symbols(unit="USD", topn=1)
        await update.message.reply_text(f"🔎 Trạng thái: {'LIVE ✅' if live else 'DOWN ❌'}")
        return

    if text == BTN_TOP:
        await top_cmd(update, context)
        return

    if text == BTN_VND:
        _current_unit = "VND"
        await update.message.reply_text("✅ Đã chuyển sang **VND**.", parse_mode=ParseMode.MARKDOWN)
        return

    if text == BTN_USD:
        _current_unit = "USD"
        await update.message.reply_text("✅ Đã chuyển sang **USD**.", parse_mode=ParseMode.MARKDOWN)
        return

    # Lịch (placeholder; bạn nối nguồn thật sau)
    if text == BTN_TODAY:
        await update.message.reply_text("📅 Lịch hôm nay: (rút gọn).")
        return
    if text == BTN_TOMORROW:
        await update.message.reply_text("📅 Lịch ngày mai: (rút gọn).")
        return
    if text == BTN_WEEK:
        await update.message.reply_text("📅 Lịch cả tuần: (rút gọn).")
        return

    if text == BTN_TEST:
        await update.message.reply_text("[TEST] Format & Scheduler ok.")
        return

# ---------------- Bootstrap ----------------
def build_app() -> Application:
    app: Application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("top", top_cmd))
    app.add_handler(CommandHandler("usd", set_usd))
    app.add_handler(CommandHandler("vnd", set_vnd))

    # Bắt text thường để xử lý menu
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), on_menu_click))

    # Lên lịch gửi tín hiệu mỗi slot
    j = app.job_queue
    for hhmm in SLOT_TIMES:
        h, m = map(int, hhmm.split(":"))
        j.run_daily(send_batch_scalping, time=dt_time(h, m, tzinfo=VN_TZ))

    return app
