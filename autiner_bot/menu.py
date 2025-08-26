from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import ContextTypes
from autiner_bot.utils import state
from autiner_bot.scheduler import job_trade_signals_notice, job_trade_signals
from autiner_bot.jobs.daily_reports import job_morning_message, job_evening_summary
from autiner_bot.data_sources.mexc import (
    get_usdt_vnd_rate,
    analyze_single_coin,
    get_top_futures
)
from autiner_bot.utils.time_utils import get_vietnam_time


# ==== Hàm tạo menu động theo trạng thái ====
def get_reply_menu():
    s = state.get_state()
    auto_btn = "🟢 Auto ON" if not s["is_on"] else "🔴 Auto OFF"
    currency_btn = "💵 MEXC USD" if s["currency_mode"] == "VND" else "💴 MEXC VND"
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


# ==== Handler cho Reply Keyboard & Coin input ====
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()

    # Bật/Tắt bot
    if text in ["🟢 auto on", "🔴 auto off"]:
        if text == "🟢 auto on":
            state.set_on_off(True)
            msg = "⚙️ Auto tín hiệu: 🟢 ON"
        else:
            state.set_on_off(False)
            msg = "⚙️ Auto tín hiệu: 🔴 OFF"
        await update.message.reply_text(msg, reply_markup=get_reply_menu())

    # Chuyển đổi đơn vị
    elif text in ["💴 mexc vnd", "💵 mexc usd"]:
        new_mode = "VND" if text == "💴 mexc vnd" else "USD"
        state.set_currency_mode(new_mode)
        await update.message.reply_text(
            f"💱 Đã chuyển đơn vị sang: {new_mode}",
            reply_markup=get_reply_menu()
        )

    # Xem trạng thái
    elif text == "🔍 trạng thái":
        s = state.get_state()
        msg = (
            f"📡 Dữ liệu MEXC: LIVE ✅\n"
            f"• Đơn vị: {s['currency_mode']}\n"
            f"• Auto: {'ON' if s['is_on'] else 'OFF'}"
        )
        await update.message.reply_text(msg, reply_markup=get_reply_menu())

    # Test bot
    elif text == "🧪 test":
        await update.message.reply_text("🔍 Đang test toàn bộ tính năng...")
        await job_morning_message()
        await job_trade_signals_notice()
        await job_trade_signals()
        await job_evening_summary()
        await update.message.reply_text("✅ Test toàn bộ tính năng hoàn tất!", reply_markup=get_reply_menu())

    # Nếu nhập tên coin bất kỳ
    else:
        all_coins = await get_top_futures(limit=200)  # lấy nhiều coin
        symbols = [c["symbol"] for c in all_coins]

        query = text.upper()
        symbol = None

        # Nếu nhập đúng hẳn (vd: BTC → BTC_USDT)
        if f"{query}_USDT" in symbols:
            symbol = f"{query}_USDT"
        else:
            # Nếu nhập ngắn (vd: pepe → PEPE1000_USDT)
            for s in symbols:
                if s.startswith(query):
                    symbol = s
                    break

        if not symbol:
            await update.message.reply_text(f"⚠️ Coin {query} không tồn tại trên MEXC Futures", reply_markup=get_reply_menu())
            return

        s = state.get_state()
        vnd_rate = await get_usdt_vnd_rate() if s["currency_mode"] == "VND" else None
        trend = await analyze_coin_trend(symbol)

        if not trend:
            await update.message.reply_text(f"⚠️ Không phân tích được cho {symbol}", reply_markup=get_reply_menu())
            return

        entry = trend.get("lastPrice", 0)
        entry_price = entry * vnd_rate if vnd_rate else entry
        tp = entry * (1.01 if trend["side"] == "LONG" else 0.99)
        sl = entry * (0.99 if trend["side"] == "LONG" else 1.01)
        tp_price = tp * vnd_rate if vnd_rate else tp
        sl_price = sl * vnd_rate if vnd_rate else sl

        msg = (
            f"📈 {symbol.replace('_USDT','/'+s['currency_mode'])} — "
            f"{'🟢 LONG' if trend['side']=='LONG' else '🟥 SHORT'}\n\n"
            f"🔹 Kiểu vào lệnh: Market\n"
            f"💰 Entry: {entry_price:,.2f} {s['currency_mode']}\n"
            f"🎯 TP: {tp_price:,.2f} {s['currency_mode']}\n"
            f"🛡️ SL: {sl_price:,.2f} {s['currency_mode']}\n"
            f"📊 Độ mạnh: {trend['strength']:.1f}%\n"
            f"📌 Lý do: {trend['reason']}\n"
            f"🕒 Thời gian: {get_vietnam_time().strftime('%H:%M %d/%m/%Y')}"
        )
        await update.message.reply_text(msg, reply_markup=get_reply_menu())
