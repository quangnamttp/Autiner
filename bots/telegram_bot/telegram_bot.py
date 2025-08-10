import logging
from telegram.ext import Application, CommandHandler, ContextTypes
from settings import TELEGRAM_BOT_TOKEN, ALLOWED_USER_ID
from bots.handlers import top
from bots.telegram_bot.onus_api import cache_status

logging.basicConfig(format="%(asctime)s %(levelname)s: %(message)s", level=logging.INFO)

async def start(update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID:
        return
    await update.message.reply_text("🤖 Bot ONUS sẵn sàng.\nGõ /top để xem top coin.")

async def status_cmd(update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID:
        return
    st = cache_status()
    live = "LIVE ✅" if st.get("live") else "CACHE"
    age = st.get("age_sec")
    await update.message.reply_text(f"📶 Nguồn: {live}\n⏱ Tuổi cache: {age}s")

def build_app():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status_cmd))
    top.register_top_handler(app)
    top.start_top_updater()
    return app

# placeholder nếu web.py có gọi
async def send_signals(app):
    return
