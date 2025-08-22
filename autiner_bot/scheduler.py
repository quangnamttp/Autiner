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
def rsi(values, period=14):
    if len(values) < period + 1:
        return 50
    deltas = np.diff(values)
    ups = deltas.clip(min=0)
    downs = -1 * deltas.clip(max=0)
    avg_gain = np.mean(ups[-period:])
    avg_loss = np.mean(downs[-period:]) if np.mean(downs[-period:]) != 0 else 1e-10
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

# =============================
# MACD
# =============================
def macd(values, short=12, long=26, signal=9):
    if len(values) < long + signal:
        return 0, 0
    ema_short = ema(values, short)
    ema_long = ema(values, long)
    macd_line = ema_short - ema_long
    signal_line = ema(values[-signal:], signal)
    return macd_line, signal_line

# =============================
# Quyết định xu hướng với EMA + RSI + MACD
# =============================
def decide_direction_with_indicators(klines: list):
    if not klines or len(klines) < 26:
        return ("LONG", True, "Không đủ dữ liệu", 0)

    closes = [k["close"] for k in klines]

    # EMA
    ema6 = ema(closes, 6)
    ema12 = ema(closes, 12)
    last = closes[-1]
    diff = abs(ema6 - ema12) / last * 100  # strength %

    # RSI
    rsi_val = rsi(closes, 14)

    # MACD
    macd_line, signal_line = macd(closes)

    reason = f"EMA6={ema6:.4f}, EMA12={ema12:.4f}, RSI={rsi_val:.2f}, MACD={macd_line:.4f}, Signal={signal_line:.4f}"

    # Xu hướng
    if ema6 > ema12:
        side = "LONG"
    else:
        side = "SHORT"

    # Kiểm tra sức mạnh xu hướng
    strong = False
    if side == "LONG" and rsi_val > 60 and macd_line > signal_line:
        strong = True
    elif side == "SHORT" and rsi_val < 40 and macd_line < signal_line:
        strong = True

    return (side, not strong, reason, diff)

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
            text="⏳ 1 phút nữa sẽ có tín hiệu giao dịch, bạn hãy kiểm tra dữ liệu trước khi vào lệnh nhé!"
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

        coin_signals = []
        for coin in all_coins:
            klines = await get_kline(coin["symbol"], limit=50, interval="Min15")
            side, weak, reason, diff = decide_direction_with_indicators(klines)

            coin_signals.append({
                "symbol": coin["symbol"],
                "side": side,
                "reason": reason,
                "strength": diff,
                "lastPrice": coin["lastPrice"],
                "weak": weak
            })

        # sắp xếp strength giảm dần
        coin_signals.sort(key=lambda x: x["strength"], reverse=True)
        top5 = coin_signals[:5]

        messages = []
        for idx, coin in enumerate(top5):
            msg = create_trade_signal(
                symbol=coin["symbol"],
                side=coin["side"],
                entry_raw=coin["lastPrice"],
                mode="Scalping",
                currency_mode=currency_mode,
                vnd_rate=vnd_rate,
                weak=coin["weak"],
                reason=coin["reason"],
                strength=round(coin["strength"], 2)
            )
            if idx == 0 and not coin["weak"]:  # coin mạnh nhất
                msg = msg.replace("📈", "📈⭐", 1)
            messages.append(msg)

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
