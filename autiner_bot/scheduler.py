from telegram import Bot
from autiner_bot.settings import S
from autiner_bot.utils.state import get_state
from autiner_bot.utils.time_utils import get_vietnam_time
from autiner_bot.data_sources.mexc import get_top_moving_coins
from autiner_bot.data_sources.exchange import get_usdt_vnd_rate
from autiner_bot.strategies.scalping import generate_scalping_signal
from autiner_bot.strategies.swing import generate_swing_signal
from autiner_bot.utils.format_utils import format_price
import traceback

bot = Bot(token=S.TELEGRAM_BOT_TOKEN)

# ----- Báo trước -----
async def job_trade_signals_notice():
    try:
        state = get_state()
        if not state["is_on"]:
            return
        await bot.send_message(
            chat_id=S.TELEGRAM_ALLOWED_USER_ID,
            text="⏳ 1 phút nữa sẽ có tín hiệu giao dịch, chuẩn bị nhé!"
        )
    except Exception as e:
        print(f"[ERROR] job_trade_signals_notice: {e}")
        print(traceback.format_exc())

# ----- Buổi sáng -----
async def job_morning_message():
    try:
        state = get_state()
        if not state["is_on"]:
            return

        now = get_vietnam_time()
        vnd_rate = None
        if state["currency_mode"] == "VND":
            vnd_rate = await get_usdt_vnd_rate()

        top_coins = await get_top_moving_coins(limit=5)
        coins_list = "\n".join(
            [f"• {c['symbol']}: {format_price(float(c['lastPrice']), state['currency_mode'], vnd_rate)}"
             for c in top_coins]
        )

        usd_to_vnd_text = ""
        if state["currency_mode"] == "VND" and vnd_rate:
            usd_to_vnd_text = f"💵 1 USD = {format_price(vnd_rate, 'VND', vnd_rate)}\n\n"

        msg = (
            f"🌞 Chào buổi sáng!\n"
            f"Hôm nay: {now.strftime('%A %d-%m-%Y')}\n\n"
            f"{usd_to_vnd_text}"
            f"📈 Top 5 coin biến động mạnh:\n{coins_list}\n\n"
            f"📢 15 phút nữa sẽ có tín hiệu!"
        )

        await bot.send_message(chat_id=S.TELEGRAM_ALLOWED_USER_ID, text=msg)
    except Exception as e:
        print(f"[ERROR] job_morning_message: {e}")
        print(traceback.format_exc())

# ----- Gửi tín hiệu -----
async def job_trade_signals():
    try:
        state = get_state()
        if not state["is_on"]:
            return

        vnd_rate = None
        if state["currency_mode"] == "VND":
            vnd_rate = await get_usdt_vnd_rate()

        moving_coins = await get_top_moving_coins(limit=8, min_volume=1_000_000, min_change=1.0)

        scalping_signals = [generate_scalping_signal(c["symbol"]) for c in moving_coins[:5]]
        swing_signals = [generate_swing_signal(c["symbol"]) for c in moving_coins[5:8]]
        all_signals = scalping_signals + swing_signals

        for sig in all_signals:
            entry_price = format_price(sig['entry'], state['currency_mode'], vnd_rate)
            tp_price = format_price(sig['tp'], state['currency_mode'], vnd_rate)
            sl_price = format_price(sig['sl'], state['currency_mode'], vnd_rate)

            side_icon = "🟥 SHORT" if sig["side"].upper() == "SHORT" else "🟩 LONG"
            highlight = "⭐ " if sig["strength"] >= 70 else ""

            msg = (
                f"{highlight}📈 {sig['symbol']} — {side_icon}\n\n"
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

# ----- Tổng kết -----
async def job_summary():
    try:
        state = get_state()
        if not state["is_on"]:
            return

        msg = (
            "🌒 Tổng kết phiên hôm nay:\n"
            "📊 Hiệu suất TP/SL: (demo)\n"
            "📉 Mua/Bán: (demo)\n\n"
            "😴 Chúc bạn ngủ ngon!"
        )
        await bot.send_message(chat_id=S.TELEGRAM_ALLOWED_USER_ID, text=msg)
    except Exception as e:
        print(f"[ERROR] job_summary: {e}")
        print(traceback.format_exc())
