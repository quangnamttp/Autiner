from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import ContextTypes
from autiner_bot.utils import state
from autiner_bot.data_sources.mexc import get_usdt_vnd_rate, get_all_futures, analyze_coin
from autiner_bot.utils.time_utils import get_vietnam_time

# ==== Menu đơn giản ====
def get_reply_menu():
    s = state.get_state()
    currency_btn = "💵 USD Mode" if s["currency_mode"] == "VND" else "💴 VND Mode"
    keyboard = [["🔍 Trạng thái", currency_btn]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ==== /start ====
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s = state.get_state()
    msg = (
        f"📡 Bot thủ công: nhập tên coin để phân tích\n"
        f"• Đơn vị hiện tại: {s['currency_mode']}"
    )
    await update.message.reply_text(msg, reply_markup=get_reply_menu())

# ==== Handler input ====
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()

    # Chuyển chế độ đơn vị
    if text in ["💴 vnd mode", "💵 usd mode"]:
        new_mode = "VND" if text == "💴 vnd mode" else "USD"
        state.set_currency_mode(new_mode)
        await update.message.reply_text(f"💱 Đã chuyển sang {new_mode}", reply_markup=get_reply_menu())
        return

    # Trạng thái
    if text == "🔍 trạng thái":
        s = state.get_state()
        await update.message.reply_text(
            f"📡 Bot thủ công\n• Đơn vị: {s['currency_mode']}",
            reply_markup=get_reply_menu()
        )
        return

    # Tìm coin theo tên gần đúng
    all_coins = await get_all_futures()
    if not all_coins:
        await update.message.reply_text("⚠️ Không lấy được dữ liệu coin từ MEXC.")
        return

    symbols = [c["symbol"] for c in all_coins]
    query = text.upper()
    symbol = None
    if f"{query}_USDT" in symbols:
        symbol = f"{query}_USDT"
    else:
        for s in symbols:
            if s.startswith(query):
                symbol = s
                break
    if not symbol:
        await update.message.reply_text(f"⚠️ Không tìm thấy {query} trên MEXC Futures")
        return

    coin = next(c for c in all_coins if c["symbol"] == symbol)
    vnd_rate = await get_usdt_vnd_rate() if state.get_state()["currency_mode"] == "VND" else None
    trend = await analyze_coin(symbol, coin["lastPrice"], coin["change_pct"], {"trend": "N/A"})

    if not trend:
        await update.message.reply_text(f"⚠️ Không phân tích được {symbol}")
        return

    entry = coin["lastPrice"]
    entry_price = entry * vnd_rate if vnd_rate else entry
    tp = entry * (1.01 if trend["side"] == "LONG" else 0.99)
    sl = entry * (0.99 if trend["side"] == "LONG" else 1.01)
    tp_price = tp * vnd_rate if vnd_rate else tp
    sl_price = sl * vnd_rate if vnd_rate else sl

    msg = (
        f"📈⭐ {symbol.replace('_USDT','/'+state.get_state()['currency_mode'])} — "
        f"{'🟢 LONG' if trend['side']=='LONG' else '🟥 SHORT'}\n\n"
        f"🔹 Kiểu vào lệnh: Market\n"
        f"💰 Entry: {entry_price:,.2f} {state.get_state()['currency_mode']}\n"
        f"🎯 TP: {tp_price:,.2f} {state.get_state()['currency_mode']}\n"
        f"🛡️ SL: {sl_price:,.2f} {state.get_state()['currency_mode']}\n"
        f"📊 Độ mạnh: {trend['strength']}%\n"
        f"📌 Lý do: {trend['reason']}\n"
        f"🕒 Thời gian: {get_vietnam_time().strftime('%H:%M %d/%m/%Y')}"
    )
    await update.message.reply_text(msg, reply_markup=get_reply_menu())
