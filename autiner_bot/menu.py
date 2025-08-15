from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import ContextTypes
from autiner_bot.utils import state

def get_main_menu():
    s = state.get_state()
    currency_label = "💵 MEXC USD" if s["currency_mode"] == "USD" else "💴 MEXC VND"
    status_label = "🟢 Auto ON" if s["is_on"] else "🔴 Auto OFF"

    keyboard = [
        ["📊 Trạng thái", status_label],
        ["🧪 Test", currency_label]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 Xin chào! Đây là bot Autiner",
        reply_markup=get_main_menu()
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "📊 Trạng thái":
        s = state.get_state()
        await update.message.reply_text(
            f"📡 Dữ liệu MEXC: LIVE ✅\n• Đơn vị: {s['currency_mode']}\n• Auto: {'ON' if s['is_on'] else 'OFF'}"
        )
    elif text == "🟢 Auto ON":
        state.set_on_off(True)
        await update.message.reply_text("⚙️ Auto tín hiệu: 🟢 ON")
    elif text == "🔴 Auto OFF":
        state.set_on_off(False)
        await update.message.reply_text("⚙️ Auto tín hiệu: 🔴 OFF")
    elif text == "💵 MEXC USD":
        state.set_currency_mode("USD")
        await update.message.reply_text("💱 Đã chuyển sang: USD")
    elif text == "💴 MEXC VND":
        state.set_currency_mode("VND")
        await update.message.reply_text("💱 Đã chuyển sang: VND")
    elif text == "🧪 Test":
        await update.message.reply_text("✅ Bot hoạt động bình thường!")
