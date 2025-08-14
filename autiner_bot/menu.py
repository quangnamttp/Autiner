from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from autiner_bot.utils import state


def get_main_menu():
    """Tạo menu chính"""
    keyboard = [
        [
            InlineKeyboardButton("🔄 Bật/Tắt bot", callback_data="toggle"),
            InlineKeyboardButton("📊 Trạng thái", callback_data="status"),
        ],
        [
            InlineKeyboardButton("🧪 Test bot", callback_data="test"),
        ],
        [
            InlineKeyboardButton("💵 MEXC USD", callback_data="set_usd"),
            InlineKeyboardButton("💴 MEXC VND", callback_data="set_vnd"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lệnh /start để hiển thị menu"""
    await update.message.reply_text(
        "Xin chào! Đây là bot Autiner 🚀\nChọn chức năng bên dưới:",
        reply_markup=get_main_menu()
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý khi bấm các nút"""
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "toggle":
        new_status = state.toggle_on_off()
        await query.edit_message_text(
            f"✅ Bot đã {'BẬT' if new_status else 'TẮT'}",
            reply_markup=get_main_menu()
        )

    elif data == "status":
        s = state.get_state()
        await query.edit_message_text(
            f"📊 Trạng thái: {'BẬT' if s['is_on'] else 'TẮT'}\n💱 Chế độ: {s['currency_mode']}",
            reply_markup=get_main_menu()
        )

    elif data == "test":
        await query.edit_message_text(
            "🧪 Bot hoạt động bình thường!",
            reply_markup=get_main_menu()
        )

    elif data == "set_usd":
        state.set_currency_mode("USD")
        await query.edit_message_text(
            "💵 Đã chuyển sang chế độ MEXC USD",
            reply_markup=get_main_menu()
        )

    elif data == "set_vnd":
        state.set_currency_mode("VND")
        await query.edit_message_text(
            "💴 Đã chuyển sang chế độ MEXC VND",
            reply_markup=get_main_menu()
        )
