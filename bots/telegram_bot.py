import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from config.settings import TELEGRAM_BOT_TOKEN
from features.scheduler import schedule_loop
from features.signals import get_batch_messages

# UID mặc định của bạn
ALLOWED_USER_ID = 5335165612

def is_allowed(update: Update) -> bool:
    return update.effective_user and update.effective_user.id == ALLOWED_USER_ID

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    await update.message.reply_text("autiner đã sẵn sàng. Lịch 06:15 → 21:45 (VN).")

async def whoami(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id if update.effective_user else None
    chat_id = update.effective_chat.id if update.effective_chat else None
    await update.message.reply_text(f"UID: {uid}\nChat ID: {chat_id}")

async def demo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    for m in get_batch_messages():
        await update.message.reply_text(m)
        await asyncio.sleep(0.6)

async def run_scheduler(app):
    await schedule_loop(app.bot)

def build_app():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("whoami", whoami))
    app.add_handler(CommandHandler("demo", demo))
    asyncio.get_event_loop().create_task(run_scheduler(app))
    return app
