from telegram import Bot
from autiner_bot.settings import S
from autiner_bot.utils.state import get_state
from autiner_bot.utils.time_utils import get_vietnam_time
from autiner_bot.data_sources.mexc import (
    get_usdt_vnd_rate,
    get_top_futures,
    analyze_coin_trend
)
from autiner_bot.jobs.daily_reports import job_morning_message, job_evening_summary

import traceback
import pytz
from datetime import time

bot = Bot(token=S.TELEGRAM_BOT_TOKEN)


# =============================
# Format giá (không làm tròn, không có 0. hoặc ,0)
# =============================
def format_price(value: float, currency: str = "USD", vnd_rate: float | None = None) -> str:
    try:
        if currency == "VND":
            if not vnd_rate or vnd_rate <= 0:
                return "N/A VND"
            value = value * vnd_rate
            # số nguyên, không có thập phân dư
            return f"{value:,.0f}".replace(",", ".")
        else:
            s = f"{value:.6f}".rstrip("0").rstrip(".")
            if float(s) >= 1:
                if "." in s:
                    int_part, dec_part = s.split(".")
                    int_part = f"{int(int_part):,}".replace(",", ".")
                    return f"{int_part}.{dec_part}" if dec_part else int_part
                else:
                    return f"{int(s):,}".replace(",", ".")
            return s
    except Exception:
        return str(value)


# =============================
# Notice trước khi ra tín hiệu
# =============================
async def job_trade_signals_notice(_=None):
    try:
        state = get_state()
        if not state["is_on"]:
            return

        all_coins = await get_top_futures(limit=15)
        if not all_coins:
            return

        coin_signals = []
        for coin in all_coins:
            trend = await analyze_coin_trend(coin["symbol"], interval="Min15", limit=50)
            coin_signals.append(trend)

        coin_signals.sort(key=lambda x: x["strength"], reverse=True)
        top5 = coin_signals[:5]

        strong_count = sum(1 for s in top5 if not s["is_weak"])
        weak_count = len(top5) - strong_count

        msg = (
            f"⏳ 1 phút nữa sẽ có tín hiệu giao dịch!\n"
            f"📊 Dự kiến: {strong_count} tín hiệu mạnh, {weak_count} tín hiệu tham khảo."
        )
        await bot.send_message(chat_id=S.TELEGRAM_ALLOWED_USER_ID, text=msg)
    except Exception as e:
        print(f"[ERROR] job_trade_signals_notice: {e}")


# =============================
# Tạo tín hiệu giao dịch
# =============================
def create_trade_signal(symbol, side, entry_raw,
                        mode="Scalping", currency_mode="USD",
                        vnd_rate=None, strength=0, reason="No data"):
    try:
        entry_price = format_price(entry_raw, currency_mode, vnd_rate)

        if side == "LONG":
            tp_val = entry_raw * (1.01 if mode == "Scalping" else 1.02)
            sl_val = entry_raw * (0.99 if mode == "Scalping" else 0.98)
        else:  # SHORT
            tp_val = entry_raw * (0.99 if mode == "Scalping" else 0.98)
            sl_val = entry_raw * (1.01 if mode == "Scalping" else 1.02)

        tp = format_price(tp_val, currency_mode, vnd_rate)
        sl = format_price(sl_val, currency_mode, vnd_rate)

        symbol_display = symbol.replace("_USDT", f"/{currency_mode.upper()}")
        strength_txt = f"{strength:.0f}%"

        msg = (
            f"📈 {symbol_display} — {'🟢 LONG' if side=='LONG' else '🟥 SHORT'}\n\n"
            f"🟢 Loại lệnh: {mode}\n"
            f"🔹 Kiểu vào lệnh: Market\n"
            f"💰 Entry: {entry_price} {currency_mode}\n"
            f"🎯 TP: {tp} {currency_mode}\n"
            f"🛡️ SL: {sl} {currency_mode}\n"
            f"📊 Độ mạnh: {strength_txt}\n"
            f"📌 Lý do: {reason}\n"
            f"🕒 Thời gian: {get_vietnam_time().strftime('%H:%M %d/%m/%Y')}"
        )
        return msg
    except Exception:
        return None


# =============================
# Gửi tín hiệu giao dịch (3 Scalping + 2 Swing)
# =============================
async def job_trade_signals(_=None):
    try:
        state = get_state()
        if not state["is_on"]:
            return

        currency_mode = state.get("currency_mode", "USD")
        vnd_rate = await get_usdt_vnd_rate() if currency_mode == "VND" else None

        all_coins = await get_top_futures(limit=20)
        if not all_coins:
            await bot.send_message(chat_id=S.TELEGRAM_ALLOWED_USER_ID,
                                   text="⚠️ Không lấy được dữ liệu coin từ sàn.")
            return

        coin_signals = []
        for coin in all_coins:
            trend = await analyze_coin_trend(coin["symbol"], interval="Min15", limit=50)
            trend["symbol"] = coin["symbol"]
            trend["lastPrice"] = coin["lastPrice"]
            coin_signals.append(trend)

        coin_signals.sort(key=lambda x: x["strength"], reverse=True)

        # ✅ lấy 5 coin mạnh nhất: 3 Scalping + 2 Swing
        top5 = coin_signals[:5]

        for idx, coin in enumerate(top5):
            mode = "Scalping" if idx < 3 else "Swing"
            msg = create_trade_signal(
                symbol=coin["symbol"],
                side=coin["side"],
                entry_raw=coin["lastPrice"],
                mode=mode,
                currency_mode=currency_mode,
                vnd_rate=vnd_rate,
                strength=coin["strength"],
                reason=coin["reason"]
            )
            # đánh dấu tín hiệu mạnh nhất
            if idx == 0:
                msg = msg.replace("📈", "📈⭐", 1)
            if msg:
                await bot.send_message(chat_id=S.TELEGRAM_ALLOWED_USER_ID, text=msg)

    except Exception as e:
        print(f"[ERROR] job_trade_signals: {e}")
        print(traceback.format_exc())


# =============================
# Setup job vào job_queue
# =============================
def setup_jobs(application):
    tz = pytz.timezone("Asia/Ho_Chi_Minh")

    application.job_queue.run_daily(job_morning_message, time=time(6, 0, 0, tzinfo=tz))
    application.job_queue.run_daily(job_evening_summary, time=time(22, 0, 0, tzinfo=tz))

    for h in range(6, 22):
        for m in [15, 45]:
            application.job_queue.run_daily(job_trade_signals_notice, time=time(h, m - 1, 0, tzinfo=tz))
            application.job_queue.run_daily(job_trade_signals, time=time(h, m, 0, tzinfo=tz))

    print("✅ Scheduler đã setup thành công!")
