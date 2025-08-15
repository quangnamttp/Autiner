from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import ContextTypes

from autiner_bot.utils import state
from autiner_bot.jobs.daily_reports import job_morning_message, job_evening_summary
from autiner_bot.scheduler import job_trade_signals


# ==== Hàm tạo menu động theo trạng thái ====
def get_reply_menu():
    s = state.get_state()

    auto_btn = "🟢 Auto ON" if not s["is_on"] else "🔴 Auto OFF"
    currency_btn = "💴 MEXC VND" if s["currency_mode"] == "VND" else "💵 MEXC USD"

    keyboard = [
        ["🔍 Trạng thái", auto_btn],
        ["🧪 Test toàn bộ", currency_btn]
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

    # Bật/Tắt bot
    if text in ["🟢 Auto ON", "🔴 Auto OFF"]:
        if text == "🟢 Auto ON":
            state.set_on_off(True)
            msg = "⚙️ Auto tín hiệu: 🟢 ON"
        else:
            state.set_on_off(False)
            msg = "⚙️ Auto tín hiệu: 🔴 OFF"
        await update.message.reply_text(msg, reply_markup=get_reply_menu())

    # Chuyển đổi đơn vị
    elif text in ["💴 MEXC VND", "💵 MEXC USD"]:
        new_mode = "USD" if state.get_state()["currency_mode"] == "VND" else "VND"
        state.set_currency_mode(new_mode)
        await update.message.reply_text(
            f"💱 Đã chuyển đơn vị sang: {new_mode}",
            reply_markup=get_reply_menu()
        )

    # Xem trạng thái
    elif text == "🔍 Trạng thái":
        s = state.get_state()
        msg = (
            f"📡 Dữ liệu MEXC: LIVE ✅\n"
            f"• Đơn vị: {s['currency_mode']}\n"
            f"• Auto: {'ON' if s['is_on'] else 'OFF'}"
        )
        await update.message.reply_text(msg, reply_markup=get_reply_menu())

    # Test toàn bộ (6h + tín hiệu + 22h)
    elif text == "🧪 Test toàn bộ":
        await update.message.reply_text("🔄 Đang chạy test toàn bộ báo cáo...", reply_markup=get_reply_menu())
        await job_morning_message()
        await job_trade_signals()
        await job_evening_summary()
        await update.message.reply_text("✅ Hoàn tất test toàn bộ!")

    else:
        await update.message.reply_text("⚠️ Lệnh không hợp lệ!", reply_markup=get_reply_menu())
