import logging
from telegram.ext import Application, CommandHandler
from settings import TELEGRAM_BOT_TOKEN, ALLOWED_USER_ID
from bots.handlers import top

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# Lệnh /start
async def start(update, context):
    if update.effective_user.id != ALLOWED_USER_ID:
        await update.message.reply_text("🚫 Bạn không có quyền sử dụng bot này.")
        return
    await update.message.reply_text("🤖 Bot Onus đã sẵn sàng!\nGõ /top để xem top coin volume cao.")

def build_app():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Lệnh cơ bản
    app.add_handler(CommandHandler("start", start))

    # Đăng ký lệnh /top
    top.register_top_handler(app)
    top.start_top_updater()  # chạy auto update dữ liệu Onus

    return app
