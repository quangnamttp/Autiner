# autiner_bot/menu.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from autiner_bot.utils import state

# ====== Hàm tạo menu chính ======
def get_main_menu():
    s = state.get_state()  # Lấy trạng thái hiện tại
    currency_btn = "💵 MEXC USD" if s["currency_mode"] == "USD" else "💴 MEXC VND"
    status_btn = "🟢 Đang BẬT" if s["is_on"] else "🔴 Đang TẮT"

    keyboard = [
        [InlineKeyboardButton(currency_btn, callback_data="toggle_currency")],
        [InlineKeyboardButton(status_btn, callback_data="toggle_on_off")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ====== Lệnh /start và /menu ======
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⚙️ Cài đặt bot Autiner", reply_markup=get_main_menu())

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⚙️ Cài đặt bot Autiner", reply_markup=get_main_menu())

# ====== Xử lý khi bấm nút ======
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "toggle_currency":
        s = state.get_state()
        if s["currency_mode"] == "USD":
            state.set_currency_mode("VND")  # Lưu lại
        else:
            state.set_currency_mode("USD")  # Lưu lại
        await query.edit_message_text("⚙️ Cài đặt bot Autiner", reply_markup=get_main_menu())

    elif data == "toggle_on_off":
        state.toggle_on_off()  # Lưu lại
        await query.edit_message_text("⚙️ Cài đặt bot Autiner", reply_markup=get_main_menu())
