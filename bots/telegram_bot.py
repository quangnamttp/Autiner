import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from config.settings import TELEGRAM_BOT_TOKEN, ALLOWED_USER_ID, TZ_NAME
from storage.state import is_allowed_user
from features.scheduler import schedule_loop

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed_user(update.effective_user.id):
        return
    await update.message.reply_text("autiner đã sẵn sàng. Lịch 06:15 → 21:45. VN timezone.")

async def demo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed_user(update.effective_user.id):
        return
    # Gửi ngay một batch thử
    from features.signals import get_batch_text
    await update.message.reply_text(get_batch_text())

async def run_scheduler(app):
    # Dùng bot của Application để chạy scheduler nền
    bot = app.bot
    await schedule_loop(bot)

def build_app():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("demo", demo))
    # Khởi động scheduler nền
    asyncio.get_event_loop().create_task(run_scheduler(app))
    return app
