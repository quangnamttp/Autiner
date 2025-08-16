# autiner_bot/scheduler/scheduler.py
from telegram import Bot
from autiner_bot.settings import S
from autiner_bot.utils.state import get_state
from autiner_bot.utils.time_utils import get_vietnam_time
from autiner_bot.data_sources.mexc import get_usdt_vnd_rate
from autiner_bot.strategies.trend_detector import detect_trend
from autiner_bot.strategies.signal_analyzer import analyze_coin_signal
from autiner_bot.jobs.daily_reports import job_morning_message, job_evening_summary

import traceback
import pytz
from datetime import time

bot = Bot(token=S.TELEGRAM_BOT_TOKEN)


# =============================
# Hàm format giá
# =============================
def format_price(value: float, currency: str = "USD", vnd_rate: float | None = None) -> str:
    try:
        if currency == "VND":
            if not vnd_rate or vnd_rate <= 0:
                return "N/A VND"
            value = value * vnd_rate
            if value >= 1000:
                return f"{value:,.0f}".replace(",", ".")
            elif value >= 1:
                return f"{value:.4f}".rstrip("0").rstrip(".")
            else:
                return str(int(value))
        else:  # USD
            if value >= 1:
                return f"{value:,.2f}"
            else:
                return f"{value:.6f}"
    except Exception:
        return str(value)


# =============================
# Tạo tín hiệu giao dịch
# =============================
async def create_trade_signal(coin: dict, mode: str = "SCALPING", currency_mode="USD", vnd_rate=None):
    last_price = coin.get("lastPrice", 0.0)
    signal = analyze_coin_signal(coin)

    tp_price = last_price * (1 + signal["tp_pct"] / 100)
    sl_price = last_price * (1 + signal["sl_pct"] / 100)

    entry_price = format_price(last_price, currency_mode, vnd_rate)
    tp_price = format_price(tp_price, currency_mode, vnd_rate)
    sl_price = format_price(sl_price, currency_mode, vnd_rate)

    # Hiển thị symbol + side
    symbol_display = coin["symbol"].replace("_USDT", f"/{currency_mode}")
    side_icon = "🟩 LONG" if signal["direction"] == "LONG" else "🟥 SHORT"
    highlight = "⭐" if signal["strength"] >= 70 else ""

    # Trend coin (nếu detect_trend có gán)
    trend_name = coin.get("trend", "Khác")
    trade_style = mode.upper()  # SCALPING hoặc SWING

    msg = (
        f"{highlight}📈 {symbol_display}\n"
        f"{side_icon} - {trade_style}\n"
        f"🔹 Trend: {trend_name}\n"
        f"🔹 Kiểu vào lệnh: {signal['orderType'].upper()}\n"
        f"💰 Entry: {entry_price} {currency_mode}\n"
        f"🎯 TP: {tp_price} {currency_mode}\n"
        f"🛡️ SL: {sl_price} {currency_mode}\n"
        f"📊 Độ mạnh: {signal['strength']}%\n"
        f"📌 Lý do: {signal['reason']}\n"
        f"🕒 {get_vietnam_time().strftime('%H:%M %d/%m/%Y')}"
    )
    return msg


# =============================
# Báo trước 1 phút
# =============================
async def job_trade_signals_notice(_=None):
    try:
        state = get_state()
        if not state["is_on"]:
            return
        await bot.send_message(
            chat_id=S.TELEGRAM_ALLOWED_USER_ID,
            text="⏳ 1 phút nữa sẽ có tín hiệu giao dịch!"
        )
    except Exception as e:
        print(f"[ERROR] job_trade_signals_notice: {e}")
        print(traceback.format_exc())


# =============================
# Gửi tín hiệu giao dịch
# =============================
async def job_trade_signals(_=None):
    try:
        state = get_state()
        if not state["is_on"]:
            return

        currency_mode = state.get("currency_mode", "USD")
        vnd_rate = None
        if currency_mode == "VND":
            vnd_rate = await get_usdt_vnd_rate()
            if not vnd_rate or vnd_rate <= 0:
                await bot.send_message(
                    chat_id=S.TELEGRAM_ALLOWED_USER_ID,
                    text="⚠️ Không lấy được tỷ giá USDT/VND. Tín hiệu bị hủy."
                )
                return

        coins = await detect_trend(limit=5)  # lọc coin mạnh theo trend
        if not coins:
            await bot.send_message(
                chat_id=S.TELEGRAM_ALLOWED_USER_ID,
                text="⚠️ Không tìm được coin đủ điều kiện để tạo tín hiệu."
            )
            return

        # 3 Scalping (top 3) + 2 Swing (top 4-5)
        for i, coin in enumerate(coins):
            mode = "SCALPING" if i < 3 else "SWING"
            msg = await create_trade_signal(coin, mode, currency_mode, vnd_rate)
            await bot.send_message(chat_id=S.TELEGRAM_ALLOWED_USER_ID, text=msg)

    except Exception as e:
        print(f"[ERROR] job_trade_signals: {e}")
        print(traceback.format_exc())


# =============================
# Đăng ký job sáng, tối và tín hiệu
# =============================
def register_daily_jobs(job_queue):
    tz = pytz.timezone("Asia/Ho_Chi_Minh")

    # Báo cáo sáng
    job_queue.run_daily(job_morning_message, time=time(hour=6, minute=0, tzinfo=tz), name="morning_report")

    # Báo cáo tối
    job_queue.run_daily(job_evening_summary, time=time(hour=22, minute=0, tzinfo=tz), name="evening_report")

    # Lặp tín hiệu 30 phút
    job_queue.run_repeating(
        job_trade_signals_notice,
        interval=1800,  # 30 phút
        first=time(hour=6, minute=14, tzinfo=tz),
        name="signal_notice"
    )
    job_queue.run_repeating(
        job_trade_signals,
        interval=1800,  # 30 phút
        first=time(hour=6, minute=15, tzinfo=tz),
        name="trade_signals"
    )
