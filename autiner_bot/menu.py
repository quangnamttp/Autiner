# autiner_bot/menu.py
from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import ContextTypes
from autiner_bot.utils import state

# ==== Hàm tạo menu động theo trạng thái ====
def get_reply_menu():
    s = state.get_state()

    auto_btn = "🟢 Auto ON" if s["is_on"] else "🔴 Auto OFF"
    currency_btn = "💴 MEXC VND" if s["currency_mode"] == "VND" else "💵 MEXC USD"

    keyboard = [
        ["🔍 Trạng thái", auto_btn],
        ["🧪 Test", currency_btn]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ==== /start Command ====
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s = state.get_state()
    msg = (
        f"📡 Dữ liệu MEXC: LIVE ✅\n"
        f"• Đơn vị: {s['currency_mode']}\n"
        f"• Auto: {'ON' if s['is_on'] else 'OFF'}"
    )
    await update.message.reply_text(msg, reply_markup=get_reply_menu())

# ==== Handler cho Reply Keyboard ====
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if text in ["🟢 Auto ON", "🔴 Auto OFF"]:
        new_status = not state.get_state()["is_on"]
        state.set_on_off(new_status)
        await update.message.reply_text(
            f"⚙️ Auto tín hiệu: {'🟢 ON' if new_status else '🔴 OFF'}",
            reply_markup=get_reply_menu()
        )

    elif text in ["💴 MEXC VND", "💵 MEXC USD"]:
        new_mode = "USD" if state.get_state()["currency_mode"] == "VND" else "VND"
        state.set_currency_mode(new_mode)
        await update.message.reply_text(
            f"💱 Đã chuyển đơn vị sang: {new_mode}",
            reply_markup=get_reply_menu()
        )

    elif text == "🔍 Trạng thái":
        s = state.get_state()
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
