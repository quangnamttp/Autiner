import random
import traceback
import pytz
from datetime import time
from telegram import Bot

from autiner_bot.settings import S
from autiner_bot.utils.state import get_state
from autiner_bot.utils.time_utils import get_vietnam_time
from autiner_bot.data_sources.mexc import (
    get_usdt_vnd_rate,
    get_top_futures,
    get_market_sentiment,
)
from autiner_bot.jobs.daily_reports import job_morning_message, job_evening_summary

bot = Bot(token=S.TELEGRAM_BOT_TOKEN)

# =============================
# Format giá
# =============================
def format_price(value: float, currency: str = "USD", vnd_rate: float | None = None) -> str:
    try:
        if currency == "VND":
            if not vnd_rate or vnd_rate <= 0:
                return "N/A VND"
            value = value * vnd_rate
            return f"{value:,.0f}".replace(",", ".")
        else:
            return f"{value:.6f}".rstrip("0").rstrip(".")
    except Exception:
        return str(value)


# =============================
# Notice trước khi ra tín hiệu
# =============================
async def job_trade_signals_notice(_=None):
    state = get_state()
    if not state["is_on"]:
        return
    await bot.send_message(
        chat_id=S.TELEGRAM_ALLOWED_USER_ID,
        text="⏳ 1 phút nữa sẽ có tín hiệu giao dịch, chuẩn bị sẵn sàng nhé!"
    )


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

        all_coins = await get_top_futures(limit=15)
        sentiment = await get_market_sentiment()

        if not all_coins:
            await bot.send_message(chat_id=S.TELEGRAM_ALLOWED_USER_ID,
                                   text="⚠️ Không lấy được dữ liệu coin từ MEXC.")
            return

        # Xác định xu hướng thị trường
        if abs(sentiment["long"] - sentiment["short"]) <= 10:
            market_trend = "LONG"
            sideway = True
        else:
            market_trend = "LONG" if sentiment["long"] > sentiment["short"] else "SHORT"
            sideway = False

        # Random 5 coin trong top 15
        selected = random.sample(all_coins, min(5, len(all_coins)))

        if not selected:
            await bot.send_message(chat_id=S.TELEGRAM_ALLOWED_USER_ID,
                                   text="⚠️ Không có tín hiệu hợp lệ trong phiên này.")
            return

        for i, coin in enumerate(selected):
            mode = "SCALPING" if i < 3 else "SWING"
            entry_price = format_price(coin["lastPrice"], currency_mode, vnd_rate)
            symbol_display = coin["symbol"].replace("_USDT", f"/{currency_mode.upper()}")
            side_icon = "🟩 LONG" if market_trend == "LONG" else "🟥 SHORT"

            if sideway:
                label = "⚠️ THAM KHẢO (SIDEWAY) ⚠️"
            else:
                label = "⭐ TÍN HIỆU THEO XU HƯỚNG ⭐"

            msg = (
                f"{label}\n"
                f"📈 {symbol_display}\n"
                f"{side_icon}\n"
                f"📌 Chế độ: {mode}\n"
                f"💰 Entry: {entry_price} {currency_mode}\n"
                f"🎯 TP/SL: Theo trend\n"
                f"🕒 {get_vietnam_time().strftime('%H:%M %d/%m/%Y')}"
            )

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
