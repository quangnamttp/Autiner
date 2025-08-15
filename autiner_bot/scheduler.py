from telegram import Bot
from autiner_bot.settings import S
from autiner_bot.utils.state import get_state
from autiner_bot.utils.time_utils import get_vietnam_time
from autiner_bot.data_sources.mexc import get_top_moving_coins
from autiner_bot.data_sources.exchange import get_usdt_vnd_rate
from autiner_bot.utils.format_utils import format_price
import traceback

bot = Bot(token=S.TELEGRAM_BOT_TOKEN)

def create_trade_signal(symbol, last_price, change_pct):
    """Tạo tín hiệu LONG/SHORT + Market/Limit."""
    direction = "LONG" if change_pct > 0 else "SHORT"
    order_type = "MARKET" if abs(change_pct) > 2 else "LIMIT"

    tp_pct = 0.5 if direction == "LONG" else -0.5
    sl_pct = -0.3 if direction == "LONG" else 0.3

    tp_price = last_price * (1 + tp_pct / 100)
    sl_price = last_price * (1 + sl_pct / 100)

    return {
        "symbol": symbol,
        "side": direction,
        "type": "Futures",
        "orderType": order_type,
        "entry": last_price,
        "tp": tp_price,
        "sl": sl_price,
        "strength": min(int(abs(change_pct) * 10), 100),
        "reason": f"Biến động {change_pct:.2f}% trong 15 phút"
    }

async def job_trade_signals_notice():
    try:
        state = get_state()
        if not state["is_on"]:
            return
        await bot.send_message(
            chat_id=S.TELEGRAM_ALLOWED_USER_ID,
            text="⏳ 1 phút nữa sẽ có tín hiệu giao dịch từ bộ lọc biến động!"
        )
    except Exception as e:
        print(f"[ERROR] job_trade_signals_notice: {e}")
        print(traceback.format_exc())

async def job_trade_signals():
    try:
        state = get_state()
        if not state["is_on"]:
            return

        vnd_rate = None
        if state["currency_mode"] == "VND":
            vnd_rate = await get_usdt_vnd_rate()

        moving_coins = await get_top_moving_coins(limit=5, min_turnover=500000)
        signals = [create_trade_signal(c["symbol"], c["lastPrice"], c["change_pct"]) for c in moving_coins]

        for sig in signals:
            entry_price = format_price(sig['entry'], state['currency_mode'], vnd_rate)
            tp_price = format_price(sig['tp'], state['currency_mode'], vnd_rate)
            sl_price = format_price(sig['sl'], state['currency_mode'], vnd_rate)

            # Hiển thị symbol dạng /VND hoặc /USD
            suffix = "/VND" if state["currency_mode"] == "VND" else "/USD"
            symbol_display = sig['symbol'].replace("_USDT", suffix)

            side_icon = "🟥 SHORT" if sig["side"] == "SHORT" else "🟩 LONG"
            highlight = "⭐ " if sig["strength"] >= 70 else ""

            msg = (
                f"{highlight}📈 {symbol_display} — {side_icon}\n\n"
                f"🟢 Loại lệnh: {sig['type']}\n"
                f"🔹 Kiểu vào lệnh: {sig['orderType']}\n"
                f"💰 Entry: {entry_price}\n"
                f"🎯 TP: {tp_price}\n"
                f"🛡️ SL: {sl_price}\n"
                f"📊 Độ mạnh: {sig['strength']}%\n"
                f"📌 Lý do: {sig['reason']}\n"
                f"🕒 Thời gian: {get_vietnam_time().strftime('%H:%M %d/%m/%Y')}"
            )

            await bot.send_message(chat_id=S.TELEGRAM_ALLOWED_USER_ID, text=msg)
    except Exception as e:
        print(f"[ERROR] job_trade_signals: {e}")
        print(traceback.format_exc())
