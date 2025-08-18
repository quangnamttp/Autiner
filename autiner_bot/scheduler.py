from telegram import Bot
from autiner_bot.settings import S
from autiner_bot.utils.state import get_state
from autiner_bot.utils.time_utils import get_vietnam_time
from autiner_bot.data_sources.mexc import (
    get_usdt_vnd_rate,
    analyze_coin_signal_v2,
    get_top20_futures,
    get_market_sentiment,
)
from autiner_bot.jobs.daily_reports import job_morning_message, job_evening_summary

import traceback
import pytz
import random
from datetime import time

bot = Bot(token=S.TELEGRAM_BOT_TOKEN)
_last_selected = []


# =============================
# Format giá
# =============================
def format_price(value: float, currency: str = "USD", vnd_rate: float | None = None) -> str:
    try:
        if currency == "VND":
            if not vnd_rate or vnd_rate <= 0:
                return "N/A VND"
            value = value * vnd_rate
            if value >= 1_000_000:
                return f"{round(value):,}".replace(",", ".")
            else:
                return f"{value:,.2f}".replace(",", ".")
        else:
            s = f"{value:.6f}".rstrip("0").rstrip(".")
            if float(s) >= 1:
                if "." in s:
                    int_part, dec_part = s.split(".")
                    int_part = f"{int(int_part):,}".replace(",", ".")
                    s = f"{int_part}.{dec_part}"
                else:
                    s = f"{int(s):,}".replace(",", ".")
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
        await bot.send_message(
            chat_id=S.TELEGRAM_ALLOWED_USER_ID,
            text="⏳ 1 phút nữa sẽ có tín hiệu giao dịch, chuẩn bị sẵn sàng nhé!"
        )
    except Exception as e:
        print(f"[ERROR] job_trade_signals_notice: {e}")


# =============================
# Tạo tín hiệu giao dịch
# =============================
async def create_trade_signal(coin: dict, mode: str = "SCALPING", currency_mode="USD", vnd_rate=None):
    try:
        signal = await analyze_coin_signal_v2(coin)
        if not signal or signal["entry"] <= 0:
            return None

        entry_price = format_price(signal["entry"], currency_mode, vnd_rate)
        tp_price = format_price(signal["tp"], currency_mode, vnd_rate)
        sl_price = format_price(signal["sl"], currency_mode, vnd_rate)

        symbol_display = coin["symbol"].replace("_USDT", f"/{currency_mode.upper()}")
        side_icon = "🟩 LONG" if signal["direction"] == "LONG" else "🟥 SHORT"

        if signal["strength"] >= 70:
            label = "⭐ TÍN HIỆU MẠNH ⭐"
        elif signal["strength"] <= 60:
            label = "⚠️ THAM KHẢO ⚠️"
        else:
            label = ""

        msg = (
            f"{label}\n"
            f"📈 {symbol_display}\n"
            f"{side_icon}\n"
            f"📌 Chế độ: {mode.upper()}\n"
            f"📑 Loại lệnh: {signal['orderType']}\n"
            f"💰 Entry: {entry_price} {currency_mode}\n"
            f"🎯 TP: {tp_price} {currency_mode}\n"
            f"🛡️ SL: {sl_price} {currency_mode}\n"
            f"📊 Độ mạnh: {signal['strength']}%\n"
            f"📌 Lý do:\n{signal['reason']}\n"
            f"🕒 {get_vietnam_time().strftime('%H:%M %d/%m/%Y')}"
        )
        return msg
    except Exception as e:
        print(f"[ERROR] create_trade_signal: {e}")
        print(traceback.format_exc())
        return None


# =============================
# Gửi tín hiệu giao dịch
# =============================
async def job_trade_signals(_=None):
    global _last_selected
    try:
        state = get_state()
        if not state["is_on"]:
            return

        currency_mode = state.get("currency_mode", "USD")
        vnd_rate = None
        if currency_mode == "VND":
            vnd_rate = await get_usdt_vnd_rate()
            if not vnd_rate or vnd_rate <= 0:
                await bot.send_message(chat_id=S.TELEGRAM_ALLOWED_USER_ID, text="⚠️ Không lấy được tỷ giá USDT/VND. Tín hiệu bị hủy.")
                return

        all_coins = await get_top20_futures(limit=20)
        sentiment = await get_market_sentiment()
        if not all_coins:
            await bot.send_message(chat_id=S.TELEGRAM_ALLOWED_USER_ID, text="⚠️ Không lấy được dữ liệu coin từ sàn.")
            return

        market_trend = "LONG" if sentiment["long"] > sentiment["short"] else "SHORT"
