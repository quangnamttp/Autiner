# bot.py
import asyncio
import logging
from datetime import datetime
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

def build_reply_keyboard():
    return ReplyKeyboardMarkup(
        [
            ["🔍 Trạng thái", "🟢 Auto ON" if STATE["AUTO_ON"] else "🔴 Auto OFF"],
            ["🧪 Test", "💵 MEXC USD", "💵 MEXC VND"]
        ],
        resize_keyboard=True
    )

# ==== Lấy tỷ giá ====
async def get_usd_vnd():
    async with httpx.AsyncClient() as client:
        r = await client.get(settings.MEXC_TICKER_VNDC_URL, timeout=5)
        data = r.json()
        return float(data["data"][0]["last"])

# ==== Tín hiệu mẫu ====
async def generate_signals():
    usd_vnd = await get_usd_vnd()
    signals = []
    for i in range(5):
        price_usd = 0.00021 * (i + 1)
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
        await asyncio.sleep(0.3)

# ==== Báo cáo sáng/tối ====
async def send_morning_report(context: ContextTypes.DEFAULT_TYPE):
    usd_vnd = await get_usd_vnd()
    txt = f"☀️ Chào buổi sáng!\nTỷ giá USDT/VND hôm nay: {usd_vnd}"
    await context.bot.send_message(chat_id=settings.TELEGRAM_ALLOWED_USER_ID, text=txt)

async def send_night_summary(context: ContextTypes.DEFAULT_TYPE):
    txt = "🌙 Tổng kết cuối ngày..."
    await context.bot.send_message(chat_id=settings.TELEGRAM_ALLOWED_USER_ID, text=txt)

# ==== Start ====
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Bot tín hiệu MEXC đã sẵn sàng!",
        reply_markup=build_reply_keyboard()
    )

# ==== Reply Keyboard xử lý ====
async def handle_reply_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    chat_id = update.effective_chat.id

    if text.startswith("🔍 Trạng thái"):
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"Auto: {'ON' if STATE['AUTO_ON'] else 'OFF'}\nCurrency: {STATE['CURRENCY']}\nTime: {vn_now()}",
            reply_markup=build_reply_keyboard()
        )
    elif text.startswith("🟢 Auto ON") or text.startswith("🔴 Auto OFF"):
        STATE["AUTO_ON"] = not STATE["AUTO_ON"]
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"Auto: {'ON' if STATE['AUTO_ON'] else 'OFF'}",
            reply_markup=build_reply_keyboard()
        )
    elif text.startswith("🧪 Test"):
        # Test toàn bộ chức năng
        await context.bot.send_message(chat_id=chat_id, text="🔄 Đang test toàn bộ bot...")
        await handle_reply_buttons(update=Update(update.update_id, update.message), context=context)  # trạng thái
        await send_signal_batch(context, chat_id)
        await send_morning_report(context)
        await send_night_summary(context)
    elif text.startswith("💵 MEXC USD"):
        await context.bot.send_message(chat_id=chat_id, text="1 USDT = 1 USD", reply_markup=build_reply_keyboard())
    elif text.startswith("💵 MEXC VND"):
        usd_vnd = await get_usd_vnd()
        await context.bot.send_message(chat_id=chat_id, text=f"1 USDT = {usd_vnd}₫", reply_markup=build_reply_keyboard())

# ==== Auto Scheduler ====
async def auto_loop(app: Application):
    while True:
        now = vn_now()
        if STATE["AUTO_ON"]:
            if now.strftime("%H:%M") == "06:00":
                await send_morning_report(app.bot)
            elif now.strftime("%H:%M") == "22:00":
                await send_night_summary(app.bot)
            elif now.minute in [15, 45] and 6 <= now.hour < 22:
                await send_signal_batch(app.bot)
        await asyncio.sleep(60)

# ==== Run bot ====
async def run_bot():
    app = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_reply_buttons))
    asyncio.create_task(auto_loop(app))
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    await asyncio.Event().wait()
