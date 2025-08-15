# autiner_bot/menu.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from autiner_bot.utils import state

def get_main_menu():
    s = state.get_state()
    btn_onoff = "🔴 Tắt bot" if s["is_on"] else "🟢 Bật bot"
    btn_currency = "💵 MEXC USD" if s["currency_mode"] == "USD" else "💴 MEXC VND"

    keyboard = [
        [
            InlineKeyboardButton(btn_onoff, callback_data="toggle"),
            InlineKeyboardButton("📊 Trạng thái", callback_data="status"),
        ],
        [
            InlineKeyboardButton("🧪 Test bot", callback_data="test"),
        ],
        [
            InlineKeyboardButton(btn_currency, callback_data="toggle_currency"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Xin chào! Đây là bot Autiner 🚀", reply_markup=get_main_menu())

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📋 Menu điều khiển:", reply_markup=get_main_menu())

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "toggle":
        new_status = state.toggle_on_off()
        await query.edit_message_text(f"Bot đã {'BẬT' if new_status else 'TẮT'}", reply_markup=get_main_menu())

    elif data == "status":
        s = state.get_state()
        await query.edit_message_text(
            f"📊 Trạng thái bot:\n"
            f"- Hoạt động: {'BẬT' if s['is_on'] else 'TẮT'}\n"
            f"- Chế độ giá: {s['currency_mode']}",
            reply_markup=get_main_menu()
        )

    elif data == "test":
        await query.edit_message_text("✅ Bot hoạt động bình thường!", reply_markup=get_main_menu())

    elif data == "toggle_currency":
        s = state.get_state()
        new_mode = "VND" if s["currency_mode"] == "USD" else "USD"
        state.set_currency_mode(new_mode)
        await query.edit_message_text(f"💱 Đã chuyển sang {new_mode}", reply_markup=get_main_menu())
