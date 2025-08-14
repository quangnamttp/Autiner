# autiner_bot/scheduler.py
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
            print("[JOB] Bot đang tắt, bỏ qua morning message.")
            return

        now = get_vietnam_time()
        vnd_price = None
        if state["currency_mode"] == "VND":
            vnd_price = await get_usdt_vnd_rate()

        top_coins = await get_top_coins_by_volume(limit=5)
        if not top_coins:
            await bot.send_message(chat_id=S.TELEGRAM_ALLOWED_USER_ID, text="⚠️ Không lấy được danh sách coin sáng nay.")
            return

        coins_list = "\n".join(
            [f"• {c['symbol']}: {format_price(float(c['lastPrice']), state['currency_mode'])}" for c in top_coins]
        )

        msg = (
            f"🌞 Chào buổi sáng!\n"
            f"Hôm nay: {now.strftime('%A %d-%m-%Y')}\n\n"
            f"💵 1 USD = {format_price(vnd_price, 'VND') if vnd_price else 'N/A'}\n\n"
            f"📈 Top 5 coin nổi bật:\n{coins_list}\n\n"
            f"📢 15 phút nữa sẽ có tín hiệu, bạn chuẩn bị nhé!"
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
            print("[JOB] Bot đang tắt, bỏ qua tín hiệu.")
            return

        top_coins = await get_top_coins_by_volume(limit=5)
        if not top_coins:
            await bot.send_message(chat_id=S.TELEGRAM_ALLOWED_USER_ID, text="⚠️ Không lấy được coin để tạo tín hiệu.")
            return

        # 3 Scalping
        scalping_signals = [generate_scalping_signal(c["symbol"]) for c in top_coins[:3]]
        # 2 Swing
        swing_signals = [generate_swing_signal(c["symbol"]) for c in top_coins[3:5]]

        all_signals = scalping_signals + swing_signals
        msgs = []

        for sig in all_signals:
            highlight = "⭐ " if sig["strength"] >= 70 else ""

            # Format giá
            entry_price = format_price(sig['entry'], state['currency_mode'])
            tp_price = format_price(sig['tp'], state['currency_mode'])
            sl_price = format_price(sig['sl'], state['currency_mode'])

            msgs.append(
                f"{highlight}📈 {sig['symbol']} – {sig['side']}\n"
                f"🔹 {sig['type']} | {sig['orderType']}\n"
                f"💰 Entry: {entry_price}\n"
                f"🎯 TP: {tp_price}\n"
                f"🛡️ SL: {sl_price}\n"
                f"📊 Độ mạnh: {sig['strength']}%\n"
                f"📌 Lý do: {sig['reason']}\n"
                f"🕒 {get_vietnam_time().strftime('%H:%M:%S')}"
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
            print("[JOB] Bot đang tắt, bỏ qua tổng kết.")
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
