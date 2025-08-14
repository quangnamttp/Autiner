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
from bots.pricing.onus_format import display_price

log = logging.getLogger(__name__)

STATE = {"AUTO_ON": True, "CURRENCY": "VND"}  # "USD" hoặc "VND"

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
    await update.message.reply_text("🤖 Bot tín hiệu MEXC đã sẵn sàng!", reply_markup=_build_menu())

async def status_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    now = _now_vn().strftime("%d/%m/%Y %H:%M:%S")
    txt = f"🔎 Trạng thái\n- Auto: {'ON' if STATE['AUTO_ON'] else 'OFF'}\n- Đơn vị: {STATE['CURRENCY']}\n- Bây giờ: {now}"
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
    await send_signal_batch(context.bot, update.effective_chat.id)

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

def _is_slot_now(now: datetime, slot_dt: datetime, tol_sec: int = 30):
    return abs((now - slot_dt).total_seconds()) <= tol_sec

async def send_signal_batch(bot, chat_id: int):
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

async def _auto_loop(app):
    chat_id = settings.TELEGRAM_ALLOWED_USER_ID
    while True:
        if STATE["AUTO_ON"]:
            now = _now_vn()
            for slot in _slot_times():
                if _is_slot_now(now, slot):
                    await app.bot.send_message(chat_id=chat_id, text="⏳ Chuẩn bị gửi tín hiệu sau 60s…")
                    await asyncio.sleep(60)
                    await send_signal_batch(app.bot, chat_id)
                    break
        await asyncio.sleep(1)

async def run_bot(webhook_mode=False):
    application = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start_cmd))
    application.add_handler(CallbackQueryHandler(status_cb, pattern="^status$"))
    application.add_handler(CallbackQueryHandler(toggle_auto_cb, pattern="^toggle_auto$"))
    application.add_handler(CallbackQueryHandler(toggle_ccy_cb, pattern="^toggle_ccy$"))
    application.add_handler(CallbackQueryHandler(test_cb, pattern="^test$"))

    application.create_task(_auto_loop(application))

    if webhook_mode:
        await application.bot.set_webhook(settings.WEBHOOK_URL)
        log.info(f"Webhook set: {settings.WEBHOOK_URL}")
    else:
        await application.initialize()
        await application.start()
        await application.updater.start_polling()
        await asyncio.Event().wait()

async def handle_webhook(data: dict):
    from telegram import Update
    application = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
