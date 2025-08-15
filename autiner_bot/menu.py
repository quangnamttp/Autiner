from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import ContextTypes
from autiner_bot.utils import state

# ==== Reply Keyboard (Menu cố định) ====
def get_reply_menu():
    keyboard = [
        ["🔍 Trạng thái", "🟢 Auto ON", "🔴 Auto OFF"],
        ["🧪 Test", "💴 MEXC VND", "💵 MEXC USD"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ==== Inline Keyboard (Nếu cần dùng) ====
def get_inline_menu():
    keyboard = [
        [InlineKeyboardButton("🔄 Bật/Tắt bot", callback_data="toggle"),
         InlineKeyboardButton("📊 Trạng thái", callback_data="status")],
        [InlineKeyboardButton("🧪 Test bot", callback_data="test")],
        [InlineKeyboardButton("💵 MEXC USD", callback_data="set_usd"),
         InlineKeyboardButton("💴 MEXC VND", callback_data="set_vnd")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ==== /start Command ====
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s = state.get_state()
    msg = (
        f"⚙️ Dữ liệu MEXC: LIVE ✅\n"
        f"• Đơn vị: {s['currency_mode']}\n"
        f"• Auto: {'ON' if s['is_on'] else 'OFF'}"
    )
    await update.message.reply_text(msg, reply_markup=get_reply_menu())

# ==== Reply Keyboard Handler ====
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    s = state.get_state()

    if text == "🟢 Auto ON":
        state.set_on_off(True)
        await update.message.reply_text("⚙️ Auto tín hiệu: 🟢 ON", reply_markup=get_reply_menu())

    elif text == "🔴 Auto OFF":
        state.set_on_off(False)
        await update.message.reply_text("⚙️ Auto tín hiệu: 🔴 OFF", reply_markup=get_reply_menu())

    elif text == "💵 MEXC USD":
        state.set_currency_mode("USD")
        await update.message.reply_text("💵 Đã chuyển đơn vị sang: USD", reply_markup=get_reply_menu())

    elif text == "💴 MEXC VND":
        state.set_currency_mode("VND")
        await update.message.reply_text("💴 Đã chuyển đơn vị sang: VND", reply_markup=get_reply_menu())

    elif text == "🔍 Trạng thái":
        msg = (
            f"📡 Dữ liệu MEXC: LIVE ✅\n"
            f"• Đơn vị: {s['currency_mode']}\n"
            f"• Auto: {'ON' if s['is_on'] else 'OFF'}"
        )
        await update.message.reply_text(msg, reply_markup=get_reply_menu())

    elif text == "🧪 Test":
        await update.message.reply_text("✅ Bot hoạt động bình thường!", reply_markup=get_reply_menu())

    else:
        await update.message.reply_text("⚠️ Lệnh không hợp lệ!", reply_markup=get_reply_menu())

# ==== Inline Keyboard Handler ====
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "toggle":
        new_status = state.toggle_on_off()
        await query.edit_message_text(f"Bot đã {'BẬT' if new_status else 'TẮT'}", reply_markup=get_inline_menu())

    elif data == "status":
        s = state.get_state()
        await query.edit_message_text(f"Trạng thái: {'BẬT' if s['is_on'] else 'TẮT'}\nChế độ: {s['currency_mode']}", reply_markup=get_inline_menu())

    elif data == "test":
        await query.edit_message_text("✅ Bot hoạt động bình thường!", reply_markup=get_inline_menu())

    elif data == "set_usd":
        state.set_currency_mode("USD")
        await query.edit_message_text("💵 Đã chuyển sang chế độ USD", reply_markup=get_inline_menu())

    elif data == "set_vnd":
        state.set_currency_mode("VND")
        await query.edit_message_text("💴 Đã chuyển sang chế độ VND", reply_markup=get_inline_menu())
