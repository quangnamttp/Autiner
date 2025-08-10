import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
from config.settings import TELEGRAM_BOT_TOKEN, ALLOWED_USER_ID
from features.scheduler import schedule_loop
from features.signals import get_batch_messages

def is_allowed(update: Update) -> bool:
    return update.effective_user and update.effective_user.id == ALLOWED_USER_ID

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id if update.effective_user else None
    if not is_allowed(update):
        await update.message.reply_text(f"UID {uid} chưa có quyền. Dùng /whoami để lấy UID và cập nhật ALLOWED_USER_ID.")
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

async def echo_log(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id if update.effective_user else None
    txt = update.message.text if update.message else None
    print(f"[MSG] from {uid}: {txt}")

async def run_scheduler(app):
    await schedule_loop(app.bot)

def build_app():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("whoami", whoami))
    app.add_handler(CommandHandler("demo", demo))
    app.add_handler(MessageHandler(filters.ALL, echo_log))
    # Scheduler chủ động gửi tín hiệu (không phụ thuộc webhook/polling)
    asyncio.get_event_loop().create_task(run_scheduler(app))
    return app
