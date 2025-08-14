# bot.py
import asyncio
import logging
from datetime import datetime, timedelta
import pytz
import httpx
from settings import settings
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from decimal import Decimal, ROUND_DOWN

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

STATE = {
    "AUTO_ON": True,
    "CURRENCY": "VND"
}

# ==== Công thức format giá ONUS ====
def format_price_usd_vnd(price_usd: float, usd_vnd: float) -> str:
    price_vnd = price_usd * usd_vnd
    if price_vnd < 0.001:
        denom = 1_000_000
    elif price_vnd < 1:
        denom = 1_000
    else:
        denom = 1

    display_price = price_vnd * denom
    if denom == 1:
        if display_price >= 100_000:
            fmt = Decimal(display_price).quantize(Decimal("1"), rounding=ROUND_DOWN)
        elif display_price >= 1_000:
            fmt = Decimal(display_price).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
        else:
            fmt = Decimal(display_price).quantize(Decimal("0.0001"), rounding=ROUND_DOWN)
    else:
        fmt = display_price
    return f"{fmt}₫"

# ==== Hàm tiện ích ====
def vn_now():
    return datetime.now(pytz.timezone(settings.TZ_NAME))

def build_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔎 Trạng thái", callback_data="status"),
            InlineKeyboardButton("🟢 Auto ON" if STATE["AUTO_ON"] else "🔴 Auto OFF", callback_data="toggle_auto"),
        ],
        [
            InlineKeyboardButton("💱 USD/VND", callback_data="toggle_ccy"),
            InlineKeyboardButton("🧪 Test", callback_data="test"),
        ]
    ])

def build_reply_keyboard():
    return ReplyKeyboardMarkup(
        [
            ["🔍 Trạng thái", "🟢 Auto ON" if STATE["AUTO_ON"] else "🔴 Auto OFF"],
            ["🧪 Test", "💵 MEXC USD"]
        ],
        resize_keyboard=True
    )

# ==== Xử lý callback ====
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Bot tín hiệu MEXC đã sẵn sàng!",
        reply_markup=build_reply_keyboard()
    )

async def status_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    txt = f"Auto: {'ON' if STATE['AUTO_ON'] else 'OFF'}\nCurrency: {STATE['CURRENCY']}\nTime: {vn_now()}"
    await q.edit_message_text(txt, reply_markup=build_menu())

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
    await send_signal_batch(context, update.effective_chat.id)

# ==== Lấy tỷ giá USDT/VND ====
async def get_usd_vnd():
    async with httpx.AsyncClient() as client:
        r = await client.get(settings.MEXC_TICKER_VNDC_URL, timeout=5)
        data = r.json()
        return float(data["data"][0]["last"])

# ==== Lấy tín hiệu giả lập ====
async def generate_signals():
    usd_vnd = await get_usd_vnd()
    signals = []
    for i in range(5):
        price_usd = 0.00021 * (i+1)
        price_vnd_fmt = format_price_usd_vnd(price_usd, usd_vnd)
        signals.append({
            "token": f"COIN{i+1}USDT",
            "side": "LONG" if i % 2 == 0 else "SHORT",
            "entry": f"{price_usd} USD | {price_vnd_fmt}",
            "tp": "...",
            "sl": "...",
            "reason": "Phân tích kỹ thuật & volume"
        })
    return signals

# ==== Gửi tín hiệu ====
async def send_signal_batch(context: ContextTypes.DEFAULT_TYPE, chat_id=None):
    chat_id = chat_id or settings.TELEGRAM_ALLOWED_USER_ID
    sigs = await generate_signals()
    for s in sigs:
        msg = f"📈 {s['token']} – {s['side']}\n💰 Entry: {s['entry']}\n📌 {s['reason']}"
        await context.bot.send_message(chat_id=chat_id, text=msg)
        await asyncio.sleep(0.5)

# ==== Gửi báo cáo sáng ====
async def send_morning_report(context: ContextTypes.DEFAULT_TYPE):
    usd_vnd = await get_usd_vnd()
    txt = f"☀️ Chào buổi sáng!\nTỷ giá USDT/VND hôm nay: {usd_vnd}"
    await context.bot.send_message(chat_id=settings.TELEGRAM_ALLOWED_USER_ID, text=txt)

# ==== Gửi báo cáo tối ====
async def send_night_summary(context: ContextTypes.DEFAULT_TYPE):
    txt = "🌙 Tổng kết cuối ngày..."
    await context.bot.send_message(chat_id=settings.TELEGRAM_ALLOWED_USER_ID, text=txt)

# ==== Xử lý nút Reply Keyboard ====
async def handle_reply_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.startswith("🔍 Trạng thái"):
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text=f"Auto: {'ON' if STATE['AUTO_ON'] else 'OFF'}\nCurrency: {STATE['CURRENCY']}\nTime: {vn_now()}",
                                       reply_markup=build_reply_keyboard())
    elif text.startswith("🟢 Auto ON") or text.startswith("🔴 Auto OFF"):
        STATE["AUTO_ON"] = not STATE["AUTO_ON"]
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text=f"Auto: {'ON' if STATE['AUTO_ON'] else 'OFF'}",
                                       reply_markup=build_reply_keyboard())
    elif text.startswith("🧪 Test"):
        await send_signal_batch(context, update.effective_chat.id)
    elif text.startswith("💵 MEXC USD"):
        usd_vnd = await get_usd_vnd()
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text=f"Tỷ giá USDT/VND: {usd_vnd}",
                                       reply_markup=build_reply_keyboard())

# ==== Scheduler ====
async def auto_loop(app: Application):
    while True:
        now = vn_now()
        if STATE["AUTO_ON"]:
            if now.strftime("%H:%M") in ["06:00"]:
                await send_morning_report(app.bot)
            elif now.strftime("%H:%M") in ["22:00"]:
                await send_night_summary(app.bot)
            elif now.minute in [15, 45] and 6 <= now.hour < 22:
                await send_signal_batch(app.bot)
        await asyncio.sleep(60)

# ==== Run bot ====
async def run_bot():
    app = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CallbackQueryHandler(status_cb, pattern="^status$"))
    app.add_handler(CallbackQueryHandler(toggle_auto_cb, pattern="^toggle_auto$"))
    app.add_handler(CallbackQueryHandler(toggle_ccy_cb, pattern="^toggle_ccy$"))
    app.add_handler(CallbackQueryHandler(test_cb, pattern="^test$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_reply_buttons))
    asyncio.create_task(auto_loop(app))
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    await asyncio.Event().wait()
