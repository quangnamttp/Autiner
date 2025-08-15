from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from autiner_bot.utils import state

def get_main_menu():
    s = state.get_state()
    currency_label = "💵 MEXC USD" if s["currency_mode"] == "USD" else "💴 MEXC VND"
    status_label = "🟢 Bot ON" if s["is_on"] else "🔴 Bot OFF"

    keyboard = [
        [
            InlineKeyboardButton(status_label, callback_data="toggle_on_off"),
            InlineKeyboardButton(currency_label, callback_data="toggle_currency"),
        ],
        [
            InlineKeyboardButton("🧪 Test bot", callback_data="test"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 Xin chào! Đây là bot Autiner",
        reply_markup=get_main_menu()
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "toggle_on_off":
        new_status = state.toggle_on_off()
        await query.edit_message_text(
            f"✅ Bot đã {'BẬT' if new_status else 'TẮT'}",
            reply_markup=get_main_menu()
        )

    elif data == "toggle_currency":
        new_mode = state.toggle_currency_mode()
        await query.edit_message_text(
            f"💱 Đã chuyển sang chế độ {new_mode}",
            reply_markup=get_main_menu()
        )

    elif data == "test":
        await query.edit_message_text(
            "✅ Bot hoạt động bình thường!",
            reply_markup=get_main_menu()
        )
