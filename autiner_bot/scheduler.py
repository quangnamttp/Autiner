from telegram import Bot
from autiner_bot.settings import S
from autiner_bot.utils.state import get_state
from autiner_bot.utils.time_utils import get_vietnam_time
from autiner_bot.data_sources.mexc import (
    get_usdt_vnd_rate,
    get_top_futures,
    analyze_market_trend,
    analyze_single_coin,
)

import traceback
import pytz
from datetime import time

bot = Bot(token=S.TELEGRAM_BOT_TOKEN)


# =============================
# Format giá
# =============================
def format_price(value, currency="USD", vnd_rate=None):
    try:
        if currency == "VND" and vnd_rate:
            value = value * vnd_rate
            return f"{value:,.0f}".replace(",", ".")
        else:
            return f"{value:.6f}".rstrip("0").rstrip(".")
    except:
        return str(value)


# =============================
# Notice trước khi ra tín hiệu
# =============================
async def job_trade_signals_notice(_=None):
    try:
        state = get_state()
        if not state["is_on"]:
            return
        msg = "⏳ 1 phút nữa sẽ có tín hiệu giao dịch, chuẩn bị sẵn sàng!"
        await bot.send_message(chat_id=S.TELEGRAM_ALLOWED_USER_ID, text=msg)
    except Exception as e:
        print(f"[ERROR] job_trade_signals_notice: {e}")


# =============================
# Tạo tín hiệu
# =============================
def create_trade_signal(symbol, side, entry, mode,
                        currency_mode, vnd_rate, strength, reason):
    entry_price = format_price(entry, currency_mode, vnd_rate)
    tp = format_price(entry * (1.01 if side == "LONG" else 0.99), currency_mode, vnd_rate)
    sl = format_price(entry * (0.99 if side == "LONG" else 1.01), currency_mode, vnd_rate)

    return (
        f"📈 {symbol.replace('_USDT','/'+currency_mode)} — "
        f"{'🟢 LONG' if side=='LONG' else '🟥 SHORT'}\n\n"
        f"🟢 Loại lệnh: {mode}\n"
        f"🔹 Kiểu vào lệnh: Market\n"
        f"💰 Entry: {entry_price} {currency_mode}\n"
        f"🎯 TP: {tp} {currency_mode}\n"
        f"🛡️ SL: {sl} {currency_mode}\n"
        f"📊 Độ mạnh: {strength}%\n"
        f"📌 Lý do: {reason}\n"
        f"🕒 Thời gian: {get_vietnam_time().strftime('%H:%M %d/%m/%Y')}"
    )


# =============================
# Gửi tín hiệu
# =============================
async def job_trade_signals(_=None):
    try:
        state = get_state()
        if not state["is_on"]:
            return

        currency_mode = state.get("currency_mode", "USD")
        vnd_rate = await get_usdt_vnd_rate() if currency_mode == "VND" else None
        market_trend = await analyze_market_trend()

        all_coins = await get_top_futures(limit=50)
        if not all_coins:
            await bot.send_message(S.TELEGRAM_ALLOWED_USER_ID, "⚠️ Không lấy được dữ liệu coin.")
            return

        signals = []
        for coin in all_coins:
            ai_signal = await analyze_single_coin(coin["symbol"], interval="Min15", limit=50)
            if ai_signal:
                ai_signal["symbol"] = coin["symbol"]
                ai_signal["price"] = coin["lastPrice"]
                signals.append(ai_signal)

        # lấy 5 tín hiệu mạnh nhất
        signals.sort(key=lambda x: x.get("strength", 0), reverse=True)
        top5 = signals[:5]

        for idx, sig in enumerate(top5):
            mode = "Scalping" if idx < 3 else "Swing"
            msg = create_trade_signal(
                sig["symbol"],
                sig.get("side", "LONG"),
                sig["price"],
                mode,
                currency_mode,
                vnd_rate,
                sig.get("strength", 50),
                sig.get("reason", "AI phân tích")
            )
            if idx == 0:
                msg = msg.replace("📈", "📈⭐", 1)
            await bot.send_message(S.TELEGRAM_ALLOWED_USER_ID, msg)

    except Exception as e:
        print(f"[ERROR] job_trade_signals: {e}")
        print(traceback.format_exc())


# =============================
# Setup job
# =============================
def setup_jobs(application):
    tz = pytz.timezone("Asia/Ho_Chi_Minh")

    # Tín hiệu: 06:15 → 21:45 (mỗi 30 phút)
    for h in range(6, 22):
        for m in [15, 45]:
            # báo trước 1 phút
            notice_m = m - 1
            application.job_queue.run_daily(job_trade_signals_notice, time=time(h, notice_m, 0, tzinfo=tz))
            application.job_queue.run_daily(job_trade_signals, time=time(h, m, 0, tzinfo=tz))

    print("✅ Scheduler đã setup thành công!")
