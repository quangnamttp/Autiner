import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from config.settings import TELEGRAM_BOT_TOKEN, ALLOWED_USER_ID
from storage.state import is_allowed_user
from features.scheduler import schedule_loop
from features.signals import get_batch_messages

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed_user(update.effective_user.id):
        return
    await update.message.reply_text("autiner đã sẵn sàng. Lịch 06:15 → 21:45. VN timezone.")

async def demo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed_user(update.effective_user.id):
        return
    for m in get_batch_messages():
        await update.message.reply_text(m)
        await asyncio.sleep(0.8)

async def run_scheduler(app):
    bot = app.bot
    await schedule_loop(bot)

def build_app():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("demo", demo))
    asyncio.get_event_loop().create_task(run_scheduler(app))
    return app
