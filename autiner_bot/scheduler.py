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
# RSI
# =============================
def rsi(closes, period=14):
    if len(closes) < period + 1:
        return 50
    deltas = np.diff(closes)
    ups = deltas[deltas > 0].sum() / period
    downs = -deltas[deltas < 0].sum() / period
    rs = ups / downs if downs != 0 else 0
    return 100 - (100 / (1 + rs))

# =============================
# Đánh giá tín hiệu nâng cao
# =============================
def analyze_signal(klines: list):
    if not klines or len(klines) < 20:
        return ("LONG", True, "No data", 0)

    closes = [k["close"] for k in klines]
    vols = [k["volume"] for k in klines]

    ema6 = ema(closes, 6)
    ema12 = ema(closes, 12)
    last = closes[-1]
    rsi_val = rsi(closes, 14)
    vol_ratio = vols[-1] / (np.mean(vols[-10:]) + 1e-9)

    # Xu hướng EMA
    if ema6 > ema12:
        side = "LONG"
    else:
        side = "SHORT"

    # Độ mạnh = EMA diff + Volume + RSI factor
    diff = abs(ema6 - ema12) / last * 100
    rsi_factor = 1 if 45 <= rsi_val <= 65 else 0.7
    strength = diff * vol_ratio * rsi_factor

    weak = strength < 0.2  # quá yếu coi như tham khảo
    reason = f"EMA6={ema6:.4f}, EMA12={ema12:.4f}, RSI={rsi_val:.2f}, VolRatio={vol_ratio:.2f}"

    return (side, weak, reason, strength)

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
# Gửi tín hiệu giao dịch (top 5 coin mạnh nhất)
# =============================
async def job_trade_signals(_=None):
    global _last_selected
    try:
        state = get_state()
        if not state["is_on"]:
            return

        currency_mode = state.get("currency_mode", "USD")
        vnd_rate = await get_usdt_vnd_rate() if currency_mode == "VND" else None

        all_coins = await get_top_futures(limit=15)
        if not all_coins:
            await bot.send_message(chat_id=S.TELEGRAM_ALLOWED_USER_ID,
                                   text="⚠️ Không lấy được dữ liệu coin từ sàn.")
            return

        evaluated = []
        for coin in all_coins:
            klines = await get_kline(coin["symbol"], limit=50, interval="Min15")
            side, weak, reason, strength = analyze_signal(klines)
            evaluated.append((coin, side, weak, reason, strength))

        # chọn top 5 coin strength cao nhất
        evaluated.sort(key=lambda x: x[4], reverse=True)
        selected = evaluated[:5]
        _last_selected = [s[0] for s in selected]

        messages = []
        for coin, side, weak, reason, strength in selected:
            msg = create_trade_signal(
                symbol=coin["symbol"],
                side=side,
                entry_raw=coin["lastPrice"],
                mode="Scalping",
                currency_mode=currency_mode,
                vnd_rate=vnd_rate,
                weak=weak,
                reason=reason,
                strength=round(strength, 2)
            )
            messages.append(msg)

        # gắn sao ⭐ cho tín hiệu mạnh nhất
        if messages:
            messages[0] = messages[0].replace("📈", "📈⭐", 1)

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
