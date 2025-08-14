import asyncio
import logging
from datetime import datetime, timedelta
import pytz
import httpx
from fastapi import APIRouter, Request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CallbackQueryHandler
from settings import settings
from bots.onus_format import format_price_usd_vnd

log = logging.getLogger(__name__)
router = APIRouter()

STATE = {
    "AUTO_ON": True,
    "CURRENCY": "VND"
}

VN_TZ = pytz.timezone(settings.TZ_NAME)

# Hàm thời gian
def now_vn():
    return datetime.now(VN_TZ)

def build_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔎 Trạng thái", callback_data="status"),
            InlineKeyboardButton("🟢 Auto ON" if STATE["AUTO_ON"] else "🔴 Auto OFF", callback_data="toggle_auto"),
        ],
        [
            InlineKeyboardButton("💱 MEXC VND" if STATE["CURRENCY"] == "USD" else "💱 MEXC USD", callback_data="toggle_ccy"),
            InlineKeyboardButton("🧪 Test", callback_data="test"),
        ]
    ])

# Hàm lấy tỷ giá USDT/VND
async def get_usd_vnd():
    async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT) as client:
        r = await client.get(settings.MEXC_TICKER_VNDC_URL)
        data = r.json()
        price = float(data["data"][0]["last"])
        return price

# Hàm tạo tín hiệu giả lập
async def generate_signals():
    usd_vnd = await get_usd_vnd()
    coins = [
        {"symbol": "BTC_USDT", "price_usd": 65000, "trend": "LONG"},
        {"symbol": "ETH_USDT", "price_usd": 3100, "trend": "SHORT"},
    ]
    results = []
    for c in coins:
        results.append({
            "token": c["symbol"],
            "price": format_price_usd_vnd(c["price_usd"], usd_vnd),
            "trend": c["trend"]
        })
    return results

# Gửi báo cáo sáng
async def send_morning_report(app):
    usd_vnd = await get_usd_vnd()
    msg = f"🌞 Chào buổi sáng nhé anh Trương ☀️\n\n"
    msg += f"💵 Tỷ giá hôm nay: {usd_vnd}₫/USDT\n"
    msg += f"📈 Thị trường nghiêng về LONG 65% | SHORT 35%\n\n"
    msg += "💎 Top coin nổi bật:\n"
    sigs = await generate_signals()
    for s in sigs:
        msg += f"• {s['token']}: {s['price']} ({s['trend']})\n"
    msg += "\n⏳ 15 phút nữa sẽ có tín hiệu, bạn cân nhắc vào lệnh nhé!"
    await app.bot.send_message(chat_id=settings.TELEGRAM_ALLOWED_USER_ID, text=msg)

# Gửi tín hiệu
async def send_signals(app):
    sigs = await generate_signals()
    now_str = now_vn().strftime("%H:%M")
    for s in sigs:
        msg = f"📈 {s['token']}\n💰 {s['price']}\n📊 Xu hướng: {s['trend']}\n🕒 {now_str}"
        await app.bot.send_message(chat_id=settings.TELEGRAM_ALLOWED_USER_ID, text=msg)
        await asyncio.sleep(0.5)

# Gửi báo cáo tối
async def send_night_summary(app):
    await app.bot.send_message(chat_id=settings.TELEGRAM_ALLOWED_USER_ID, text="🌙 Tổng kết ngày: thị trường biến động nhẹ, chúc ngủ ngon!")

# Auto loop
async def auto_loop(app):
    slots = []
    t = VN_TZ.localize(datetime.combine(now_vn().date(), datetime.strptime(settings.SLOT_START, "%H:%M").time()))
    end = VN_TZ.localize(datetime.combine(now_vn().date(), datetime.strptime(settings.SLOT_END, "%H:%M").time()))
    while t <= end:
        slots.append(t)
        t += timedelta(minutes=settings.SLOT_STEP_MIN)

    while True:
        if STATE["AUTO_ON"]:
            now = now_vn()
            for slot in slots:
                if abs((now - slot).total_seconds()) < 30:
                    await send_signals(app)
                    break
        await asyncio.sleep(1)

# Callback
async def button_callback(update: Update, context):
    q = update.callback_query
    await q.answer()
    if q.data == "status":
        await q.edit_message_text(f"Auto: {STATE['AUTO_ON']}, CURRENCY: {STATE['CURRENCY']}", reply_markup=build_menu())
    elif q.data == "toggle_auto":
        STATE["AUTO_ON"] = not STATE["AUTO_ON"]
        await q.edit_message_text(f"Đã đổi trạng thái Auto", reply_markup=build_menu())
    elif q.data == "toggle_ccy":
        STATE["CURRENCY"] = "USD" if STATE["CURRENCY"] == "VND" else "VND"
        await q.edit_message_text(f"Đã đổi đơn vị hiển thị", reply_markup=build_menu())
    elif q.data == "test":
        await send_signals(context.application)

# Khởi tạo bot
def setup_bot(app):
    bot_app = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()
    bot_app.add_handler(CallbackQueryHandler(button_callback))
    asyncio.create_task(auto_loop(bot_app))
    return bot_app

# Webhook handler
@router.post("/webhook")
async def webhook_handler(request: Request):
    data = await request.json()
    update = Update.de_json(data, setup_bot(None).bot)
    await setup_bot(None).process_update(update)
    return {"ok": True}
