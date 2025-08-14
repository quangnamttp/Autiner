# bots/telegram_bot/telegram_bot.py
import asyncio
import logging
from datetime import datetime, timedelta
import pytz

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, ContextTypes, CallbackQueryHandler
)

from settings import settings
from bots.signals.signal_engine import generate_signals
from bots.pricing.morning_report import build_morning_report
from bots.pricing.night_summary import build_night_summary

log = logging.getLogger(__name__)

STATE = {
    "AUTO_ON": True,
    "CURRENCY": "VND"  # "USD" hoặc "VND"
}

# ==== TIME HELPERS ====
def _vn_tz():
    return pytz.timezone(settings.TZ_NAME)

def _now_vn():
    return datetime.now(_vn_tz())

def _slot_times():
    tz = _vn_tz()
    today = _now_vn().date()
    hh1, mm1 = map(int, settings.SLOT_START.split(":"))
    hh2, mm2 = map(int, settings.SLOT_END.split(":"))
    start = tz.localize(datetime(today.year, today.month, today.day, hh1, mm1))
    end = tz.localize(datetime(today.year, today.month, today.day, hh2, mm2))
    step = timedelta(minutes=settings.SLOT_STEP_MIN)
    slots = []
    t = start
    while t <= end:
        slots.append(t)
        t += step
    return slots

def _is_slot_now(now: datetime, slot_dt: datetime, tol_sec: int = 30) -> bool:
    return abs((now - slot_dt).total_seconds()) <= tol_sec

# ==== MENU ====
def _build_menu():
    row1 = [
        InlineKeyboardButton("🔎 Trạng thái", callback_data="status"),
        InlineKeyboardButton("🟢 Auto ON" if STATE["AUTO_ON"] else "🔴 Auto OFF", callback_data="toggle_auto"),
    ]
    row2 = [
        InlineKeyboardButton(f"💱 Đang {STATE['CURRENCY']}", callback_data="toggle_ccy"),
        InlineKeyboardButton("🧪 Test tín hiệu", callback_data="test"),
    ]
    return InlineKeyboardMarkup([row1, row2])

# ==== HANDLERS ====
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Bot tín hiệu đã sẵn sàng!", reply_markup=_build_menu())

async def status_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    now = _now_vn().strftime("%d/%m/%Y %H:%M:%S")
    txt = (
        f"🔎 Trạng thái bot\n"
        f"- Auto: {'ON' if STATE['AUTO_ON'] else 'OFF'}\n"
        f"- Đơn vị: {STATE['CURRENCY']}\n"
        f"- Bây giờ: {now}"
    )
    await q.edit_message_text(txt, reply_markup=_build_menu())

async def toggle_auto_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    STATE["AUTO_ON"] = not STATE["AUTO_ON"]
    await status_cb(update, context)

async def toggle_ccy_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    STATE["CURRENCY"] = "USD" if STATE["CURRENCY"] == "VND" else "VND"
    await status_cb(update, context)

async def test_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    await _send_signals(context.bot, update.effective_chat.id)

# ==== SENDERS ====
async def _send_signals(bot, chat_id: int):
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
        await bot.send_message(chat_id=chat_id, text=msg)
        await asyncio.sleep(0.5)

async def _send_morning(bot, chat_id: int):
    msg = build_morning_report(STATE["CURRENCY"])
    await bot.send_message(chat_id=chat_id, text=msg)

async def _send_night(bot, chat_id: int):
    msg = build_night_summary()
    await bot.send_message(chat_id=chat_id, text=msg)

# ==== AUTO LOOP ====
async def _auto_loop(app: Application):
    chat_id = settings.TELEGRAM_ALLOWED_USER_ID
    if not chat_id:
        log.warning("TELEGRAM_ALLOWED_USER_ID chưa cấu hình.")
        return
    sent_morning = False
    sent_night = False
    while True:
        now = _now_vn()
        if STATE["AUTO_ON"]:
            # Morning report
            if now.strftime("%H:%M") == "06:00" and not sent_morning:
                await _send_morning(app.bot, chat_id)
                sent_morning = True
            # Night summary
            if now.strftime("%H:%M") == "22:00" and not sent_night:
                await _send_night(app.bot, chat_id)
                sent_night = True
            # Reset flags daily
            if now.strftime("%H:%M") == "00:00":
                sent_morning = False
                sent_night = False
            # Signal slots
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
        await asyncio.sleep(20)  # Giảm tải CPU

# ==== RUN BOT ====
async def run_bot():
    logging.basicConfig(level=logging.INFO)
    app = Application.builder().token(settings.TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CallbackQueryHandler(status_cb, pattern="^status$"))
    app.add_handler(CallbackQueryHandler(toggle_auto_cb, pattern="^toggle_auto$"))
    app.add_handler(CallbackQueryHandler(toggle_ccy_cb, pattern="^toggle_ccy$"))
    app.add_handler(CallbackQueryHandler(test_cb, pattern="^test$"))
    app.create_task(_auto_loop(app))
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    await asyncio.Event().wait()
