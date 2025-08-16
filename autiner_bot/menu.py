from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import ContextTypes
from autiner_bot.utils import state

def get_reply_menu():
    s = state.get_state()
    auto_btn = "🟢 Auto ON" if not s["is_on"] else "🔴 Auto OFF"
    currency_btn = "💴 MEXC VND" if s["currency_mode"] == "VND" else "💵 MEXC USD"

    keyboard = [
        ["🔍 Trạng thái", auto_btn],
        ["🧪 Test", currency_btn]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s = state.get_state()
    msg = (
        f"📡 Dữ liệu MEXC: LIVE ✅\n"
        f"• Đơn vị: {s['currency_mode']}\n"
        f"• Auto: {'ON' if s['is_on'] else 'OFF'}"
    )
    await update.message.reply_text(msg, reply_markup=get_reply_menu())

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    # Bật/Tắt bot
    if text in ["🟢 Auto ON", "🔴 Auto OFF"]:
        state.set_on_off(text == "🟢 Auto ON")
        msg = f"⚙️ Auto tín hiệu: {'🟢 ON' if text == '🟢 Auto ON' else '🔴 OFF'}"
        await update.message.reply_text(msg, reply_markup=get_reply_menu())

    # Chuyển đổi đơn vị
    elif text in ["💴 MEXC VND", "💵 MEXC USD"]:
        new_mode = "USD" if state.get_state()["currency_mode"] == "VND" else "VND"
        state.set_currency_mode(new_mode)
        await update.message.reply_text(f"💱 Đã chuyển đơn vị sang: {new_mode}", reply_markup=get_reply_menu())

    # Xem trạng thái
    elif text == "🔍 Trạng thái":
        s = state.get_state()
        msg = (
            f"📡 Dữ liệu MEXC: LIVE ✅\n"
            f"• Đơn vị: {s['currency_mode']}\n"
            f"• Auto: {'ON' if s['is_on'] else 'OFF'}"
        )
        await update.message.reply_text(msg, reply_markup=get_reply_menu())

    # Test toàn bộ bot
    elif text == "🧪 Test":
        from autiner_bot.scheduler import job_trade_signals_notice, job_trade_signals
        from autiner_bot.jobs.daily_reports import job_morning_message, job_evening_summary
        import traceback

        try:
            await job_morning_message()       # Giả lập 6h
            await job_trade_signals_notice()  # Thông báo trước tín hiệu
            await job_trade_signals()         # 5 tín hiệu trade
            await job_evening_summary()       # Giả lập 22h
            await update.message.reply_text("✅ Test toàn bộ chức năng đã gửi xong!", reply_markup=get_reply_menu())
        except Exception as e:
            print(f"[TEST ERROR] {e}")
            print(traceback.format_exc())
            await update.message.reply_text("⚠️ Test lỗi, xem log console!", reply_markup=get_reply_menu())

    else:
        await update.message.reply_text("⚠️ Lệnh không hợp lệ!", reply_markup=get_reply_menu())
