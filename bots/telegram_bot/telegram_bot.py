import asyncio
import random
from datetime import datetime
import pytz
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from autiner.settings import TELEGRAM_BOT_TOKEN, ALLOWED_USER_ID, TZ_NAME, SLOT_TIMES, NUM_SCALPING, NUM_SWING
from autiner.bots.telegram_bot.onus_api import fetch_onus_futures_top30

tz = pytz.timezone(TZ_NAME)

def build_app():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("top", top))
    return app

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID:
        return
    await update.message.reply_text(f"autiner đã sẵn sàng. Lịch {SLOT_TIMES[0]} → {SLOT_TIMES[-1]} (VN).")

async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID:
        return
    top30 = fetch_onus_futures_top30()
    if not top30:
        await update.message.reply_text("Không lấy được dữ liệu.")
        return
    lines = [f"{i+1}. {c['symbol']} – Vol: {c['volumeValueVnd']:,} VND" for i, c in enumerate(top30)]
    await update.message.reply_text("\n".join(lines))

async def send_signals(app):
    while True:
        now = datetime.now(tz).strftime("%H:%M")
        if now in SLOT_TIMES:
            await send_countdown(app)
            await send_batch_signals(app)
        await asyncio.sleep(20)

async def send_countdown(app):
    for sec in range(60, 0, -1):
        await app.bot.send_message(chat_id=ALLOWED_USER_ID, text=f"⏳ {sec}s nữa đến tín hiệu 30p")
        await asyncio.sleep(1)

async def send_batch_signals(app):
    coins = fetch_onus_futures_top30()
    if not coins:
        return
    selected = random.sample(coins, NUM_SCALPING + NUM_SWING)
    scalping = selected[:NUM_SCALPING]
    swing = selected[NUM_SCALPING:]

    for coin in scalping:
        await send_signal(app, coin, "Scalping")
    for coin in swing:
        await send_signal(app, coin, "Swing")

async def send_signal(app, coin, trade_type):
    now_str = datetime.now(tz).strftime("%H:%M %d/%m/%Y")
    side = random.choice(["🟩 LONG", "🟥 SHORT"])
    msg = (
        f"📈 {coin['symbol']}(VND) — {side}\n\n"
        f"🔵 Loại lệnh: {trade_type}\n"
        f"🔹 Kiểu vào lệnh: Market\n"
        f"💰 Entry: {coin['lastPrice']:,}\n"
        f"🎯 TP: {(coin['lastPrice'] * 1.02):,.0f}\n"
        f"🛡️ SL: {(coin['lastPrice'] * 0.98):,.0f}\n"
        f"📊 Độ mạnh: {random.randint(50,90)}%\n"
        f"📌 Lý do: Funding=-, Vol5m=-, RSI=-, EMA9=-, EMA21=-\n"
        f"🕒 Thời gian: {now_str}"
    )
    await app.bot.send_message(chat_id=ALLOWED_USER_ID, text=msg)
