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
    await update.message.reply_text(
        "🤖 Bot Onus đã sẵn sàng!\n"
        "Gõ /top để xem top coin volume cao."
    )

def build_app():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Lệnh cơ bản
    app.add_handler(CommandHandler("start", start))

    # Lệnh /top
    top.register_top_handler(app)
    top.start_top_updater()  # Cập nhật dữ liệu coin liên tục

    return app

# --- placeholder cho scheduler tín hiệu ---
# Web.py đang gọi hàm này khi khởi động. Tạm thời để trống để tránh lỗi import.
# Khi bạn sẵn sàng bật gửi 5 tín hiệu mỗi 30’, mình sẽ thay nội dung hàm này.
async def send_signals(app):
    # Không làm gì cả (placeholder). Tránh chặn startup.
    return
