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
# EMA
# =============================
def ema(values, period):
    if not values or len(values) < period:
        return sum(values) / len(values) if values else 0
    k = 2 / (period + 1)
    ema_val = values[0]
    for v in values[1:]:
        ema_val = v * k + ema_val * (1 - k)
    return ema_val

# =============================
# Quyết định LONG/SHORT
# =============================
def decide_direction_with_ema(klines: list) -> tuple[str, bool, str, float]:
    if not klines or len(klines) < 10:   # ⬅️ đổi từ 12 -> 10
        return ("LONG", True, "No data", 0)

    closes = [k["close"] for k in klines]

    ema6 = ema(closes, 6)
    ema12 = ema(closes, 12)
    last = closes[-1]

    diff = abs(ema6 - ema12) / last * 100  # %
    reason = f"EMA6={ema6:.4f}, EMA12={ema12:.4f}, Close={last:.4f}"

    if diff < 0.3:  # dưới 0.3% coi là sideway
        return ("LONG", True, f"Sideway ({reason})", diff)

    if ema6 > ema12:
        return ("LONG", False, reason, diff)
    elif ema6 < ema12:
        return ("SHORT", False, reason, diff)
    else:
        return ("LONG", True, "No trend", diff)

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
                        mode="Scalping", currency_mode="USD",
                        vnd_rate=None, weak=False, reason="No data", strength=0):
    try:
        entry_price = format_price(entry_raw, currency_mode, vnd_rate)

        if side == "LONG":
            tp_val = entry_raw * (1.01 if mode == "Scalping" else 1.02)
            sl_val = entry_raw * (0.99 if mode == "Scalping" else 0.98)
        elif side == "SHORT":
            tp_val = entry_raw * (0.99 if mode == "Scalping" else 0.98)
            sl_val = entry_raw * (1.01 if mode == "Scalping" else 1.02)
        else:
            tp_val = sl_val = entry_raw

        tp = format_price(tp_val, currency_mode, vnd_rate)
        sl = format_price(sl_val, currency_mode, vnd_rate)

        symbol_display = symbol.replace("_USDT", f"/{currency_mode.upper()}")
        strength_txt = "Tham khảo" if weak else f"{strength:.2f}%"

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

        messages = []
        strengths = []

        for coin in selected:
            # chỉ lấy 10 nến gần nhất
            klines = await get_kline(coin["symbol"], limit=10, interval="Min15")
            side, weak, reason, diff = decide_direction_with_ema(klines)

            strength_val = 0 if weak else diff
            strengths.append(strength_val)

            msg = create_trade_signal(
                symbol=coin["symbol"],
                side=side,
                entry_raw=coin["lastPrice"],
                mode="Scalping",
                currency_mode=currency_mode,
                vnd_rate=vnd_rate,
                weak=weak,
                reason=reason,
                strength=round(strength_val, 2)
            )
            messages.append(msg)

        # gắn sao cho tín hiệu mạnh nhất
        if any(strengths):
            max_idx = strengths.index(max(strengths))
            if messages[max_idx]:
                messages[max_idx] = messages[max_idx].replace("📈", "📈⭐", 1)

        # gửi tin nhắn
        for msg in messages:
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
