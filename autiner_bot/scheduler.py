# autiner_bot/scheduler.py

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
# Config: auto align theo trend
# =============================
AUTO_ALIGN_MARKET = True          # <— BẬT thử nghiệm auto-align theo thị trường
MARKET_BIAS_THRESHOLD = 5.0       # chênh lệch % LONG vs SHORT tối thiểu để coi là có bias
SIDEWAY_COIN_THRESHOLD = 0.5      # |change_pct| < 0.5% coi là coin sideway (chỉ “Tham khảo”)

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
# Tạo tín hiệu giao dịch (hướng truyền vào)
# =============================
def create_trade_signal(coin: dict, side: str, mode: str = "SCALPING",
                        currency_mode="USD", vnd_rate=None, strength_note: str | None = None):
    """side: LONG | SHORT | SIDEWAY"""
    try:
        entry_raw = float(coin["lastPrice"])
        entry_price = format_price(entry_raw, currency_mode, vnd_rate)

        if side == "LONG":
            tp_val = entry_raw * (1.01 if mode.upper() == "SCALPING" else 1.02)
            sl_val = entry_raw * (0.99 if mode.upper() == "SCALPING" else 0.98)
            side_icon = "🟩 LONG"
        elif side == "SHORT":
            tp_val = entry_raw * (0.99 if mode.upper() == "SCALPING" else 0.98)
            sl_val = entry_raw * (1.01 if mode.upper() == "SCALPING" else 1.02)
            side_icon = "🟥 SHORT"
        else:  # SIDEWAY (vẫn đưa số để ai muốn ăn sóng nhỏ)
            tp_val = entry_raw
            sl_val = entry_raw
            side_icon = "⚠️ THAM KHẢO"

        tp = format_price(tp_val, currency_mode, vnd_rate)
        sl = format_price(sl_val, currency_mode, vnd_rate)
        symbol_display = coin["symbol"].replace("_USDT", f"/{currency_mode.upper()}")

        # Độ mạnh: nếu có note (Tham khảo) thì in đúng; ngược lại random 70–95%
        strength = strength_note if strength_note else f"{random.randint(70, 95)}%"

        msg = (
            f"📈 {symbol_display}\n"
            f"{side_icon}\n"
            f"📌 Chế độ: {mode.upper()}\n"
            f"💰 Entry: {entry_price} {currency_mode}\n"
            f"🎯 TP: {tp} {currency_mode}\n"
            f"🛑 SL: {sl} {currency_mode}\n"
            f"📊 Độ mạnh: {strength}\n"
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

        all_coins = await get_top_futures(limit=15)   # top 15 realtime
        sentiment = await get_market_sentiment()
        if not all_coins:
            await bot.send_message(chat_id=S.TELEGRAM_ALLOWED_USER_ID,
                                   text="⚠️ Không lấy được dữ liệu coin từ sàn.")
            return

        # Xác định bias thị trường (chỉ khi chênh lệch >= ngưỡng)
        market_bias = None
        if abs(sentiment["long"] - sentiment["short"]) >= MARKET_BIAS_THRESHOLD:
            market_bias = "LONG" if sentiment["long"] > sentiment["short"] else "SHORT"

        # Luôn chọn 5 coin (nếu <5 thì lấy hết)
        selected = random.sample(all_coins, min(5, len(all_coins)))
        if not selected:
            await bot.send_message(chat_id=S.TELEGRAM_ALLOWED_USER_ID,
                                   text="⚠️ Không có tín hiệu hợp lệ trong phiên này.")
            return

        _last_selected = selected

        for i, coin in enumerate(selected):
            # Hướng gốc theo coin (không dùng RSI/MA/Vol)
            change = float(coin.get("change_pct", 0.0))
            abs_change = abs(change)

            if abs_change < SIDEWAY_COIN_THRESHOLD:
                # Coin gần như đi ngang → vẫn gửi nhưng Độ mạnh: Tham khảo
                final_side = "SIDEWAY"
                strength_note = "Tham khảo"
            else:
                coin_side = "LONG" if change > 0 else "SHORT"

                # Auto align với thị trường nếu có bias mạnh
                if AUTO_ALIGN_MARKET and market_bias is not None:
                    final_side = market_bias
                else:
                    final_side = coin_side

                # Nếu final_side khác coin_side (đã flip) vẫn coi là mạnh (không ghi tham khảo)
                strength_note = None

            mode = "SCALPING"  # bạn muốn 5 lệnh/đợt đều SCALPING
            msg = create_trade_signal(coin, final_side, mode, currency_mode, vnd_rate, strength_note)
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

    # Daily sáng / tối
    application.job_queue.run_daily(job_morning_message, time=time(6, 0, 0, tzinfo=tz))
    application.job_queue.run_daily(job_evening_summary, time=time(22, 0, 0, tzinfo=tz))

    # Tín hiệu mỗi 30 phút (06:15 → 21:45)
    for h in range(6, 22):
        for m in [15, 45]:
            application.job_queue.run_daily(job_trade_signals_notice, time=time(h, m - 1, 0, tzinfo=tz))
            application.job_queue.run_daily(job_trade_signals, time=time(h, m, 0, tzinfo=tz))

    print("✅ Scheduler đã setup thành công!")
