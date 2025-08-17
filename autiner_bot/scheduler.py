from telegram import Bot
from autiner_bot.settings import S
from autiner_bot.utils.state import get_state
from autiner_bot.utils.time_utils import get_vietnam_time
from autiner_bot.data_sources.mexc import get_usdt_vnd_rate, detect_trend, analyze_coin_signal
from autiner_bot.jobs.daily_reports import job_morning_message, job_evening_summary

import traceback
import pytz
from datetime import time

bot = Bot(token=S.TELEGRAM_BOT_TOKEN)


# ===== Format giá =====
def format_price(value: float, currency: str = "USD", vnd_rate: float | None = None) -> str:
    try:
        if currency == "VND":
            if not vnd_rate or vnd_rate <= 0:
                return "N/A VND"
            value = value * vnd_rate
            return f"{value:,.0f}".replace(",", ".") if value >= 1000 else f"{value:.6f}".rstrip("0").rstrip(".")
        else:
            return f"{value:,.2f}" if value >= 1 else f"{value:.6f}".rstrip("0").rstrip(".")
    except Exception:
        return str(value)


# ===== Tạo tín hiệu =====
async def create_trade_signal(coin: dict, mode: str = "SCALPING", currency_mode="USD", vnd_rate=None):
    try:
        signal = await analyze_coin_signal(coin)

        entry_price = format_price(signal["entry"], currency_mode, vnd_rate)
        tp_price = format_price(signal["tp"], currency_mode, vnd_rate)
        sl_price = format_price(signal["sl"], currency_mode, vnd_rate)

        symbol_display = coin["symbol"].replace("_USDT", f"/{currency_mode.lower()}")
        side_icon = "🟩 LONG" if signal["direction"] == "LONG" else "🟥 SHORT"
        highlight = "⭐" if signal["strength"] >= 70 else ""

        msg = (
            f"{highlight}📈 {symbol_display}\n"
            f"{side_icon} - {mode.upper()}\n"
            f"💰 Entry: {entry_price} {currency_mode}\n"
            f"🎯 TP: {tp_price} {currency_mode}\n"
            f"🛡️ SL: {sl_price} {currency_mode}\n"
            f"📊 Độ mạnh: {signal['strength']}%\n"
            f"📌 Lý do: {signal['reason']}\n"
            f"🕒 {get_vietnam_time().strftime('%H:%M %d/%m/%Y')}"
        )
        return msg
    except Exception as e:
        print(f"[ERROR] create_trade_signal: {e}")
        print(traceback.format_exc())
        return "⚠️ Không tạo được tín hiệu cho coin này."


# ===== Gửi tín hiệu =====
async def job_trade_signals(_=None):
    try:
        state = get_state()
        if not state["is_on"]:
            return

        currency_mode = state.get("currency_mode", "USD")
        vnd_rate = await get_usdt_vnd_rate() if currency_mode == "VND" else None
        if currency_mode == "VND" and (not vnd_rate or vnd_rate <= 0):
            await bot.send_message(chat_id=S.TELEGRAM_ALLOWED_USER_ID, text="⚠️ Không lấy được tỷ giá USDT/VND. Tín hiệu bị hủy.")
            return

        coins = await detect_trend(limit=5)
        if not coins:
            await bot.send_message(chat_id=S.TELEGRAM_ALLOWED_USER_ID, text="⚠️ Không tìm được coin đủ điều kiện để tạo tín hiệu.")
            return

        # 3 Scalping + 2 Swing
        for i, coin in enumerate(coins):
            try:
                mode = "SCALPING" if i < 3 else "SWING"
                msg = await create_trade_signal(coin, mode, currency_mode, vnd_rate)
                await bot.send_message(chat_id=S.TELEGRAM_ALLOWED_USER_ID, text=msg)
            except Exception as e:
                print(f"[ERROR] gửi tín hiệu coin {coin.get('symbol')}: {e}")
                continue

    except Exception as e:
        print(f"[ERROR] job_trade_signals: {e}")
        print(traceback.format_exc())


# ===== Đăng ký job =====
def register_daily_jobs(job_queue):
    tz = pytz.timezone("Asia/Ho_Chi_Minh")

    job_queue.run_daily(job_morning_message, time=time(hour=6, minute=0, tzinfo=tz), name="morning_report")
    job_queue.run_daily(job_evening_summary, time=time(hour=22, minute=0, tzinfo=tz), name="evening_report")
    job_queue.run_repeating(job_trade_signals, interval=1800, first=time(hour=6, minute=15, tzinfo=tz), name="trade_signals")
