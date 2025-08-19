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

import traceback
import pytz
from datetime import time
import random

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
# Tạo tín hiệu giao dịch (TP/SL + hướng coin riêng lẻ)
# =============================
def create_trade_signal(coin: dict, mode: str = "SCALPING",
                        currency_mode="USD", vnd_rate=None, sideway=False):
    try:
        entry_raw = coin["lastPrice"]
        entry_price = format_price(entry_raw, currency_mode, vnd_rate)

        # 👉 Xác định hướng từ coin (riêng lẻ)
        change = coin.get("change_pct", 0)
        if change > 0:
            market_trend = "LONG"
            side_icon = "🟩 LONG"
        elif change < 0:
            market_trend = "SHORT"
            side_icon = "🟥 SHORT"
        else:
            market_trend = "⚠️ SIDEWAY"
            side_icon = "⚠️ SIDEWAY"

        # 👉 Tính TP/SL dựa trên hướng coin
        if market_trend == "LONG":
            tp_val = entry_raw * (1.01 if mode.upper() == "SCALPING" else 1.02)
            sl_val = entry_raw * (0.99 if mode.upper() == "SCALPING" else 0.98)
        elif market_trend == "SHORT":
            tp_val = entry_raw * (0.99 if mode.upper() == "SCALPING" else 0.98)
            sl_val = entry_raw * (1.01 if mode.upper() == "SCALPING" else 1.02)
        else:  # SIDEWAY
            tp_val = entry_raw
            sl_val = entry_raw

        tp = format_price(tp_val, currency_mode, vnd_rate)
        sl = format_price(sl_val, currency_mode, vnd_rate)

        symbol_display = coin["symbol"].replace("_USDT", f"/{currency_mode.upper()}")

        # 👉 Nếu thị trường chung sideway thì thêm nhãn cảnh báo
        label = "⚠️ THAM KHẢO (SIDEWAY THỊ TRƯỜNG) ⚠️" if sideway else "⭐ TÍN HIỆU ⭐"

        msg = (
            f"{label}\n"
            f"📈 {symbol_display}\n"
            f"{side_icon}\n"
            f"📌 Chế độ: {mode.upper()}\n"
            f"💰 Entry: {entry_price} {currency_mode}\n"
            f"🎯 TP: {tp} {currency_mode}\n"
            f"🛑 SL: {sl} {currency_mode}\n"
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
                await bot.send_message(chat_id=S.TELEGRAM_ALLOWED_USER_ID,
                                       text="⚠️ Không lấy được tỷ giá USDT/VND. Tín hiệu bị hủy.")
                return

        all_coins = await get_top_futures(limit=15)   # 🔥 lấy top 15 realtime
        sentiment = await get_market_sentiment()
        if not all_coins:
            await bot.send_message(chat_id=S.TELEGRAM_ALLOWED_USER_ID,
                                   text="⚠️ Không lấy được dữ liệu coin từ sàn.")
            return

        # Xác định xu hướng thị trường chung (dùng để gắn nhãn sideway thôi)
        sideway = abs(sentiment["long"] - sentiment["short"]) <= 10

        # Chọn ngẫu nhiên 5 coin trong top 15
        selected = random.sample(all_coins, min(5, len(all_coins)))

        if not selected:
            await bot.send_message(chat_id=S.TELEGRAM_ALLOWED_USER_ID,
                                   text="⚠️ Không có tín hiệu hợp lệ trong phiên này.")
            return

        _last_selected = selected
        messages = []
        for i, coin in enumerate(selected):
            mode = "SCALPING" if i < 3 else "SWING"
            msg = create_trade_signal(coin, mode, currency_mode, vnd_rate, sideway)
            if msg:
                messages.append(msg)

        if messages:
            for m in messages:
                await bot.send_message(chat_id=S.TELEGRAM_ALLOWED_USER_ID, text=m)
        else:
            await bot.send_message(chat_id=S.TELEGRAM_ALLOWED_USER_ID,
                                   text="⚠️ Không có tín hiệu hợp lệ trong phiên này.")
    except Exception as e:
        print(f"[ERROR] job_trade_signals: {e}")
        print(traceback.format_exc())


# =============================
# Setup job vào job_queue
# =============================
def setup_jobs(application):
    tz = pytz.timezone("Asia/Ho_Chi_Minh")

    # Daily sáng / tối
    application.job_queue.run_daily(job_morning_message, time=time(6, 0, 0, tzinfo=tz))
    application.job_queue.run_daily(job_evening_summary, time=time(22, 0, 0, tzinfo=tz))

    # Tín hiệu mỗi 30 phút (06:15 → 21:45)
    for h in range(6, 22):
        for m in [15, 45]:
            application.job_queue.run_daily(job_trade_signals_notice, time=time(h, m - 1, 0, tzinfo=tz))
            application.job_queue.run_daily(job_trade_signals, time=time(h, m, 0, tzinfo=tz))

    print("✅ Scheduler đã setup thành công!")
