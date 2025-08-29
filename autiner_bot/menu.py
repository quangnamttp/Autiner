from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import ContextTypes
from autiner_bot.utils import state
from autiner_bot.data_sources.mexc import get_usdt_vnd_rate, get_all_futures, analyze_coin
from autiner_bot.utils.time_utils import get_vietnam_time

# ==== Menu ====
def get_reply_menu():
    s = state.get_state()
    currency_btn = "💵 USD Mode" if s["currency_mode"] == "VND" else "💴 VND Mode"
    return ReplyKeyboardMarkup([["🔍 Trạng thái", currency_btn]], resize_keyboard=True)

# ==== /start ====
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s = state.get_state()
    msg = f"📡 Bot thủ công: nhập tên coin để phân tích\n• Đơn vị: {s['currency_mode']}"
    await update.message.reply_text(msg, reply_markup=get_reply_menu())

# ==== Xử lý input ====
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()

    # đổi đơn vị
    if text in ["💴 vnd mode", "💵 usd mode"]:
        new_mode = "VND" if text == "💴 vnd mode" else "USD"
        state.set_currency_mode(new_mode)
        await update.message.reply_text(f"💱 Đã chuyển sang {new_mode}", reply_markup=get_reply_menu())
        return

    # trạng thái
    if text == "🔍 trạng thái":
        s = state.get_state()
        await update.message.reply_text(f"📡 Bot thủ công\n• Đơn vị: {s['currency_mode']}", reply_markup=get_reply_menu())
        return

    # coin input
    all_coins = await get_all_futures()
    if not all_coins:
        await update.message.reply_text("⚠️ Không lấy được dữ liệu từ MEXC.")
        return

    query = text.upper()
    symbol = None
    for c in all_coins:
        if c["symbol"] == f"{query}_USDT" or c["symbol"].startswith(query):
            symbol = c["symbol"]; break

    if not symbol:
        await update.message.reply_text(f"⚠️ Không tìm thấy {query} trên MEXC Futures")
        return

    coin = next(c for c in all_coins if c["symbol"] == symbol)
    vnd_rate = await get_usdt_vnd_rate() if state.get_state()["currency_mode"]=="VND" else None

    trend = await analyze_coin(symbol, float(coin["lastPrice"]), float(coin["riseFallRate"])*100, {"trend":"N/A"})
    if not trend:
        await update.message.reply_text(f"⚠️ Không phân tích được {symbol}")
        return

    entry = float(coin["lastPrice"])
    entry_price = entry * vnd_rate if vnd_rate else entry
    tp = entry * (1.01 if trend["side"]=="LONG" else 0.99)
    sl = entry * (0.99 if trend["side"]=="LONG" else 1.01)
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
