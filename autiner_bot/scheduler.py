from telegram import Bot
from autiner_bot.settings import S
from autiner_bot.utils.state import get_state
from autiner_bot.utils.time_utils import get_vietnam_time
from autiner_bot.data_sources.mexc import (
    get_usdt_vnd_rate,
    get_top_futures,
    analyze_market_trend,
    analyze_coin,   # ✅ dùng 1 AI duy nhất
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
# Notice trước tín hiệu
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
# Gửi tín hiệu (5 coin biến động nhất mỗi 30 phút)
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
            ai_signal = await analyze_coin(
                symbol=coin["symbol"],
                price=coin["lastPrice"],
                change_pct=coin["change_pct"],
                market_trend=market_trend
            )
            if ai_signal:
                ai_signal["symbol"] = coin["symbol"]
                ai_signal["price"] = coin["lastPrice"]
                signals.append(ai_signal)

            if len(signals) >= 5:   # ✅ chỉ lấy đủ 5 coin AI
                break

        if not signals:
            await bot.send_message(S.TELEGRAM_ALLOWED_USER_ID, "⚠️ AI không phân tích được tín hiệu nào.")
            return

        for idx, sig in enumerate(signals[:5]):
            mode = "Scalping" if idx < 3 else "Swing"
            msg = create_trade_signal(
                sig["symbol"],
                sig.get("side", "LONG"),
                sig["price"],
                mode,
                currency_mode,
                vnd_rate,
                sig.get("strength", 70),
                sig.get("reason", "AI phân tích")
            )
            if idx == 0:
                msg = msg.replace("📈", "📈⭐", 1)
            await bot.send_message(S.TELEGRAM_ALLOWED_USER_ID, msg)

    except Exception as e:
        print(f"[ERROR] job_trade_signals: {e}")
        print(traceback.format_exc())


# =============================
# Setup job (30p 1 lần từ 6h15 - 21h45)
# =============================
def setup_jobs(application):
    tz = pytz.timezone("Asia/Ho_Chi_Minh")

    for h in range(6, 22):
        for m in [15, 45]:
            application.job_queue.run_daily(job_trade_signals_notice, time=time(h, m-1, 0, tzinfo=tz))
            application.job_queue.run_daily(job_trade_signals, time=time(h, m, 0, tzinfo=tz))

    print("✅ Scheduler đã setup thành công!")
