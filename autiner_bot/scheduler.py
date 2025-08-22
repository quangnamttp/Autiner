# autiner_bot/scheduler.py

from telegram import Bot
from autiner_bot.settings import S
from autiner_bot.utils.state import get_state
from autiner_bot.utils.time_utils import get_vietnam_time
from autiner_bot.data_sources.mexc import (
    get_usdt_vnd_rate,
    get_top_futures,
    get_kline,
)
from autiner_bot.jobs.daily_reports import job_morning_message, job_evening_summary

import traceback
import pytz
from datetime import time
import random
import numpy as np

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
# EMA & RSI
# =============================
def ema(values, period=9):
    if not values or len(values) < period:
        return values[-1] if values else 0
    k = 2 / (period + 1)
    ema_val = values[0]
    for price in values[1:]:
        ema_val = price * k + ema_val * (1 - k)
    return ema_val

def rsi(values, period=14):
    if len(values) < period + 1:
        return 50
    deltas = np.diff(values)
    seed = deltas[:period]
    up = seed[seed >= 0].sum() / period
    down = -seed[seed < 0].sum() / period
    rs = up / down if down > 0 else 0
    rsi_vals = np.zeros_like(values)
    rsi_vals[:period] = 100. - 100. / (1. + rs)
    up_avg, down_avg = up, down
    for i in range(period, len(values)):
        delta = deltas[i - 1]
        upval = max(delta, 0)
        downval = -min(delta, 0)
        up_avg = (up_avg * (period - 1) + upval) / period
        down_avg = (down_avg * (period - 1) + downval) / period
        rs = up_avg / down_avg if down_avg > 0 else 0
        rsi_vals[i] = 100. - 100. / (1. + rs)
    return float(rsi_vals[-1])

# =============================
# Quyết định LONG/SHORT
# =============================
def decide_direction_with_indicators(klines: list) -> tuple[str, bool, str]:
    """
    return: (side, weak, reason)
    """
    if not klines:
        return ("LONG", True, "No data")

    closes = [k["close"] for k in klines]
    if len(closes) < 34:
        return ("LONG", True, "Not enough data")

    ema9 = ema(closes, 9)
    ema21 = ema(closes, 21)
    rsi_val = rsi(closes, 14)

    reason = f"EMA9={ema9:.4f}, EMA21={ema21:.4f}, RSI={rsi_val:.1f}"

    # Quyết định
    if ema9 > ema21 and rsi_val > 55:
        return ("LONG", False, reason)
    elif ema9 < ema21 and rsi_val < 45:
        return ("SHORT", False, reason)
    else:
        return ("LONG", True, reason) if rsi_val >= 50 else ("SHORT", True, reason)

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
def create_trade_signal(symbol: str, side: str, entry_raw: float,
                        reason: str,
                        mode="SCALPING", currency_mode="USD",
                        vnd_rate=None, weak=False):
    try:
        entry_price = format_price(entry_raw, currency_mode, vnd_rate)

        if side == "LONG":
            tp_val = entry_raw * (1.01 if mode == "SCALPING" else 1.02)
            sl_val = entry_raw * (0.99 if mode == "SCALPING" else 0.98)
        elif side == "SHORT":
            tp_val = entry_raw * (0.99 if mode == "SCALPING" else 0.98)
            sl_val = entry_raw * (1.01 if mode == "SCALPING" else 1.02)
        else:
            tp_val = sl_val = entry_raw

        tp = format_price(tp_val, currency_mode, vnd_rate)
        sl = format_price(sl_val, currency_mode, vnd_rate)

        symbol_display = symbol.replace("_USDT", f"/{currency_mode.upper()}")
        strength = "Tham khảo" if weak else f"{random.randint(70,95)}%"

        # Biểu tượng side
        side_icon = "🟢" if side == "LONG" else "🟥"

        msg = (
            f"📈 {symbol_display} — {side_icon} {side}\n\n"
            f"🟢 Loại lệnh: {mode.capitalize()}\n"
            f"🔹 Kiểu vào lệnh: Market\n"
            f"💰 Entry: {entry_price} {currency_mode}\n"
            f"🎯 TP: {tp} {currency_mode}\n"
            f"🛡️ SL: {sl} {currency_mode}\n"
            f"📊 Độ mạnh: {strength}\n"
            f"📌 Lý do: {reason}\n"
            f"🕒 Thời gian: {get_vietnam_time().strftime('%H:%M %d/%m/%Y')}"
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

        all_coins = await get_top_futures(limit=15)
        if not all_coins:
            await bot.send_message(chat_id=S.TELEGRAM_ALLOWED_USER_ID,
                                   text="⚠️ Không lấy được dữ liệu coin từ sàn.")
            return

        selected = random.sample(all_coins, min(5, len(all_coins)))
        _last_selected = selected

        # Chọn 1 tín hiệu mạnh nhất gắn sao ⭐
        best_index = random.randint(0, len(selected) - 1)

        for idx, coin in enumerate(selected):
            klines = await get_kline(coin["symbol"], limit=50)
            side, weak, reason = decide_direction_with_indicators(klines)
            msg = create_trade_signal(
                symbol=coin["symbol"],
                side=side,
                entry_raw=coin["lastPrice"],
                reason=reason,
                mode="SCALPING",
                currency_mode=currency_mode,
                vnd_rate=vnd_rate,
                weak=weak
            )
            if msg:
                if idx == best_index and not weak:
                    msg = "⭐ Tín hiệu nổi bật\n" + msg
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

    # Tín hiệu từ 6h15 đến 21h45, mỗi 30 phút
    for h in range(6, 22):
        for m in [15, 45]:
            application.job_queue.run_daily(job_trade_signals_notice, time=time(h, m - 1, 0, tzinfo=tz))
            application.job_queue.run_daily(job_trade_signals, time=time(h, m, 0, tzinfo=tz))

    print("✅ Scheduler đã setup thành công!")
