from telegram import Bot
from autiner_bot.settings import S
from autiner_bot.utils.state import get_state
from autiner_bot.utils.time_utils import get_vietnam_time
from autiner_bot.data_sources.mexc import get_top_coins_by_volume
from autiner_bot.data_sources.exchange import get_usdt_vnd_rate
from autiner_bot.strategies.scalping import generate_scalping_signal
from autiner_bot.strategies.swing import generate_swing_signal
from autiner_bot.utils.format_utils import format_price
import traceback

bot = Bot(token=S.TELEGRAM_BOT_TOKEN)

async def job_morning_message():
    try:
        print("[JOB] Morning message running...")
        state = get_state()
        if not state["is_on"]:
            return

        now = get_vietnam_time()
        vnd_rate = None
        if state["currency_mode"] == "VND":
            vnd_rate = await get_usdt_vnd_rate()

        top_coins = await get_top_coins_by_volume(limit=5)
        coins_list = "\n".join(
            [
                f"• {c['symbol'].replace('/USDT','/VND') if state['currency_mode']=='VND' else c['symbol']}: "
                f"{format_price(float(c['lastPrice']), state['currency_mode'], vnd_rate)}"
                for c in top_coins
            ]
        )

        msg = (
            f"🌞 Chào buổi sáng!\n"
            f"Hôm nay: {now.strftime('%A %d-%m-%Y')}\n\n"
            f"💵 1 USD = {format_price(vnd_rate, 'VND', vnd_rate) if vnd_rate else 'N/A'}\n\n"
            f"📈 Top 5 coin nổi bật:\n{coins_list}\n\n"
            f"📢 15 phút nữa sẽ có tín hiệu!"
        )

        await bot.send_message(chat_id=S.TELEGRAM_ALLOWED_USER_ID, text=msg)

    except Exception as e:
        print(f"[ERROR] job_morning_message: {e}")
        print(traceback.format_exc())


async def job_trade_signals():
    try:
        print("[JOB] Trade signals running...")
        state = get_state()
        if not state["is_on"]:
            return

        vnd_rate = None
        if state["currency_mode"] == "VND":
            vnd_rate = await get_usdt_vnd_rate()

        top_coins = await get_top_coins_by_volume(limit=5)

        scalping_signals = [generate_scalping_signal(c["symbol"]) for c in top_coins[:3]]
        swing_signals = [generate_swing_signal(c["symbol"]) for c in top_coins[3:5]]

        all_signals = scalping_signals + swing_signals
        msgs = []
        for sig in all_signals:
            entry_price = format_price(sig['entry'], state['currency_mode'], vnd_rate)
            tp_price = format_price(sig['tp'], state['currency_mode'], vnd_rate)
            sl_price = format_price(sig['sl'], state['currency_mode'], vnd_rate)

            # Màu cho side
            side_color = "🟩" if sig['side'].upper() == "LONG" else "🟥"
            pair_name = sig['symbol'].replace("/USDT", "/VND") if state['currency_mode'] == "VND" else sig['symbol']

            highlight = "⭐ " if sig["strength"] >= 70 else ""
            msgs.append(
                f"{highlight}📈 {pair_name} — {side_color} {sig['side']}\n\n"
                f"🟢 Loại lệnh: {sig['type']}\n"
                f"🔹 Kiểu vào lệnh: {sig['orderType']}\n"
                f"💰 Entry: {entry_price}\n"
                f"🎯 TP: {tp_price}\n"
                f"🛡️ SL: {sl_price}\n"
                f"📊 Độ mạnh: {sig['strength']}% (Tiêu chuẩn)\n"
                f"📌 Lý do: {sig['reason']}\n"
                f"🕒 Thời gian: {get_vietnam_time().strftime('%H:%M %d/%m/%Y')}"
            )

        await bot.send_message(chat_id=S.TELEGRAM_ALLOWED_USER_ID, text="\n\n".join(msgs))

    except Exception as e:
        print(f"[ERROR] job_trade_signals: {e}")
        print(traceback.format_exc())


async def job_summary():
    try:
        print("[JOB] Summary running...")
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
