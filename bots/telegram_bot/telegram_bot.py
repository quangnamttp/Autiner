import logging
import pytz
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from settings import TELEGRAM_BOT_TOKEN, ALLOWED_USER_ID, TZ_NAME, SLOT_TIMES, NUM_SCALPING, NUM_SWING
from bots.telegram_bot.onus_api import fetch_onus_futures_top30

logger = logging.getLogger(__name__)

def build_app():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ALLOWED_USER_ID:
            return
        await update.message.reply_text("Bot đã khởi động!")

    app.add_handler(CommandHandler("start", start))
    return app

async def send_signals(app):
    tz = pytz.timezone(TZ_NAME)
    coins = await fetch_onus_futures_top30()
    # TODO: sinh 5 tín hiệu mỗi 30p từ coins
