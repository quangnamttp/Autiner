from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackContext
from autiner_bot.utils.state import toggle_state, get_state
from autiner_bot.settings import S
from autiner_bot.scheduler import job_trade_signals_notice, job_trade_signals
import asyncio

# =============================
# Menu chính
# =============================
def main_menu():
    state = get_state()
    status = "🟢 ON" if state["is_on"] else "🔴 OFF"
    keyboard = [
        [InlineKeyboardButton(status, callback_data="toggle_on_off")],
        [InlineKeyboardButton("🛠 Test bot", callback_data="test_bot")]
    ]
    return InlineKeyboardMarkup(keyboard)

# =============================
# /start
# =============================
async def start(update: Update, context: CallbackContext):
    if update.effective_user.id != S.TELEGRAM_ALLOWED_USER_ID:
        await update.message.reply_text("⛔ Bạn không có quyền sử dụng bot này.")
        return
    await update.message.reply_text("📌 Chào mừng! Đây là bot tín hiệu Autiner.", reply_markup=main_menu())

# =============================
# Xử lý callback
# =============================
async def button_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    if query.data == "toggle_on_off":
        toggle_state("is_on")
        await query.edit_message_text("⚙ Đã thay đổi trạng thái bot.", reply_markup=main_menu())

    elif query.data == "test_bot":
        await query.edit_message_text("⏳ Đang gửi tín hiệu test...")
        await asyncio.gather(job_trade_signals_notice(), job_trade_signals())
