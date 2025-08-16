from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import ContextTypes
from autiner_bot.utils import state

# ==== Hàm tạo menu động theo trạng thái ====
def get_reply_menu():
    s = state.get_state()

    auto_btn = "🟢 Auto ON" if not s["is_on"] else "🔴 Auto OFF"
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

    # Test toàn bộ bot
    elif text == "🧪 Test":
        from autiner_bot.scheduler import job_trade_signals_notice, job_trade_signals
        from autiner_bot.jobs.daily_reports import job_morning_message, job_evening_summary
        import asyncio, traceback

        await update.message.reply_text("🔄 Đang chạy test toàn bộ chức năng...", reply_markup=get_reply_menu())

        async def run_all_tests():
            steps = [
                ("job_morning_message", job_morning_message),
                ("job_trade_signals_notice", job_trade_signals_notice),
                ("job_trade_signals", job_trade_signals),
                ("job_evening_summary", job_evening_summary),
            ]

            for name, func in steps:
                try:
                    await context.bot.send_message(chat_id=update.effective_chat.id, text=f"▶️ Đang chạy {name}...")
                    await func()
                    await context.bot.send_message(chat_id=update.effective_chat.id, text=f"✅ {name} hoàn tất.")
                except Exception as e:
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text=f"⚠️ Lỗi khi chạy {name}!\n\nChi tiết: {e}"
                    )
                    print(f"[TEST ERROR] {name}: {e}")
                    print(traceback.format_exc())
                    return  # dừng test ngay khi lỗi

            await context.bot.send_message(chat_id=update.effective_chat.id, text="🎉 Tất cả job đã chạy thành công!")

        asyncio.create_task(run_all_tests())

    else:
        await update.message.reply_text("⚠️ Lệnh không hợp lệ!", reply_markup=get_reply_menu())
