# autiner_bot/menu.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackContext, CommandHandler, CallbackQueryHandler
from autiner_bot.settings import S
from autiner_bot.utils.state import get_state, set_state
from autiner_bot.scheduler import job_trade_signals

# =============================
# Tạo menu chính
# =============================
def main_menu():
    keyboard = [
        [
            InlineKeyboardButton("🟢 ON", callback_data="bot_on"),
            InlineKeyboardButton("🔴 OFF", callback_data="bot_off"),
        ],
        [
            InlineKeyboardButton("🧪 Test Bot", callback_data="bot_test"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# =============================
# Lệnh /start
# =============================
async def start(update: Update, context: CallbackContext):
    if update.effective_user.id != S.TELEGRAM_ALLOWED_USER_ID:
        return await update.message.reply_text("❌ Bạn không có quyền sử dụng bot này.")
    await update.message.reply_text("🤖 Xin chào! Chọn thao tác:", reply_markup=main_menu())

# =============================
# Xử lý callback từ menu
# =============================
async def menu_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    if query.from_user.id != S.TELEGRAM_ALLOWED_USER_ID:
        return await query.edit_message_text("❌ Bạn không có quyền sử dụng bot này.")

    state = get_state()

    if query.data == "bot_on":
        if state["is_on"]:
            await query.edit_message_text("⚡ Bot đã bật rồi!", reply_markup=main_menu())
        else:
            set_state({"is_on": True})
            await query.edit_message_text("🟢 Bot đã được bật!", reply_markup=main_menu())

    elif query.data == "bot_off":
        if not state["is_on"]:
            await query.edit_message_text("⚡ Bot đã tắt rồi!", reply_markup=main_menu())
        else:
            set_state({"is_on": False})
            await query.edit_message_text("🔴 Bot đã được tắt!", reply_markup=main_menu())

    elif query.data == "bot_test":
        await query.edit_message_text("🧪 Đang gửi tín hiệu test...")
        await job_trade_signals()

# =============================
# Đăng ký handler
# =============================
def register_handlers(app):
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(menu_handler))
