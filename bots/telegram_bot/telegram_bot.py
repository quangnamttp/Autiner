# bots/telegram_bot/telegram_bot.py
import asyncio
import logging
from datetime import datetime, timedelta
import pytz

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ContextTypes
)

from settings import settings
from bots.signals.signal_engine import generate_signals

log = logging.getLogger(__name__)

STATE = {
    "AUTO_ON": True,
    "CURRENCY": "VND"  # "USD" hoặc "VND"
}

def _vn_tz():
    return pytz.timezone(settings.TZ_NAME)

def _now_vn():
    return datetime.now(_vn_tz())

def _build_menu():
    row1 = [
        InlineKeyboardButton("🔎 Trạng thái", callback_data="status"),
        InlineKeyboardButton("🟢 Auto ON" if STATE["AUTO_ON"] else "🔴 Auto OFF", callback_data="toggle_auto"),
    ]
    row2 = [
        InlineKeyboardButton("💱 MEXC VND" if STATE["CURRENCY"] == "USD" else "💱 MEXC USD", callback_data="toggle_ccy"),
        InlineKeyboardButton("🧪 Test tín hiệu", callback_data="test"),
    ]
    return InlineKeyboardMarkup([row1, row2])

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot tín hiệu đã sẵn sàng!", reply_markup=_build_menu())

async def status_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    now = _now_vn().strftime("%d/%m/%Y %H:%M:%S")
    txt = f"🔎 Trạng thái\n- Auto: {'ON' if STATE['AUTO_ON'] else 'OFF'}\n- CURRENCY: {STATE['CURRENCY']}\n- Bây giờ: {now}"
    await q.edit_message_text(txt, reply_markup=_build_menu())

async def toggle_auto_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    STATE["AUTO_ON"] = not STATE["AUTO_ON"]
    await status_cb(update, context)

async def toggle_ccy_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    STATE["CURRENCY"] = "USD" if STATE["CURRENCY"] == "VND" else "VND"
    await status_cb(update, context)

async def test_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await _send_signals(context, update.effective_chat.id)

def _slot_times():
    tz = _vn_tz()
    today = _now_vn().date()
    hh1, mm1 = map(int, "06:15".split(":"))
    hh2, mm2 = map(int, "21:45".split(":"))
    start = tz.localize(datetime(today.year, today.month, today.day, hh1, mm1))
    end = tz.localize(datetime(today.year, today.month, today.day, hh2, mm2))
    step = timedelta(minutes=30)
    slots = []
    t = start
    while t <= end:
        slots.append(t)
        t += step
    return slots

def _is_slot_now(now: datetime, slot_dt: datetime, tol_sec: int = 30) -> bool:
    return abs((now - slot_dt).total_seconds()) <= tol_sec

async def _send_signals(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    sigs = generate_signals(unit=STATE["CURRENCY"], n=5)
    now_str = _now_vn().strftime("%H:%M")
    for s in sigs:
        msg = (
            f"📈 {s['token']} – {s['side']}\n"
            f"🔹 {s['type']} | {s['orderType']}\n"
            f"💰 Entry: {s['entry']}\n"
            f"🎯 TP: {s['tp']}\n"
            f"🛡️ SL: {s['sl']}\n"
            f"📊 Độ mạnh: {s['strength']}%\n"
            f"📌 Lý do: {s['reason']}\n"
            f"🕒 {now_str}"
        )
        await context.bot.send_message(chat_id=chat_id, text=msg)
        await asyncio.sleep(0.5)

async def _auto_loop(app: Application):
    chat_id = settings.TELEGRAM_ALLOWED_USER_ID
    if not chat_id:
        log.warning("TELEGRAM_ALLOWED_USER_ID chưa cấu hình.")
        return
    while True:
        if STATE["AUTO_ON"]:
            now = _now_vn()
            for slot in _slot_times():
                if _is_slot_now(now, slot):
                    await app.bot.send_message(chat_id=chat_id, text="⏳ Chuẩn bị gửi tín hiệu sau 60s…")
                    await asyncio.sleep(30)
                    await app.bot.send_message(chat_id=chat_id, text="⏳ 30s…")
                    await asyncio.sleep(25)
                    await app.bot.send_message(chat_id=chat_id, text="⏳ 5s…")
                    await asyncio.sleep(5)
                    await _send_signals(app.bot, chat_id)
                    break
        await asyncio.sleep(1)

# Tạo instance Application dùng webhook
application = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()
application.add_handler(CommandHandler("start", start_cmd))
application.add_handler(CallbackQueryHandler(status_cb, pattern="^status$"))
application.add_handler(CallbackQueryHandler(toggle_auto_cb, pattern="^toggle_auto$"))
application.add_handler(CallbackQueryHandler(toggle_ccy_cb, pattern="^toggle_ccy$"))
application.add_handler(CallbackQueryHandler(test_cb, pattern="^test$"))

# Chạy auto loop song song
application.job_queue.run_once(lambda ctx: asyncio.create_task(_auto_loop(application)), 1)
