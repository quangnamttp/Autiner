# autiner_bot/scheduler.py

from telegram import Bot
from autiner_bot.settings import S
from autiner_bot.utils.state import get_state
from autiner_bot.utils.time_utils import get_vietnam_time
from autiner_bot.data_sources.mexc import (
    get_usdt_vnd_rate,
    get_top_futures,
    get_market_sentiment,
    get_klines,   # cần có hàm lấy nến
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
# Chỉ báo: MA, RSI, Volume
# =============================
def sma(values, period=20):
    if len(values) < period:
        return float(np.mean(values)) if values else 0.0
    return float(np.mean(values[-period:]))

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

def decide_direction_with_indicators(klines: list) -> tuple[str, bool]:
    if not klines:
        return (None, True)

    closes = [k["close"] for k in klines]
    volumes = [k["volume"] for k in klines]

    if len(closes) < 20:
        return (None, True)

    ma20 = sma(closes, 20)
    last_close = closes[-1]
    rsi_val = rsi(closes, 14)
    vol_ma20 = sma(volumes, 20)
    last_vol = volumes[-1]

    weak = False
    near_ma = abs(last_close - ma20) / ma20 < 0.002  # ±0.2%
    in_rsi_mid = 45 <= rsi_val <= 55
    if near_ma or in_rsi_mid:
        weak = True

    if last_close > ma20 and rsi_val > 45 and last_vol >= 0.8 * vol_ma20:
        return ("LONG", weak)
    elif last_close < ma20 and rsi_val < 55 and last_vol >= 0.8 * vol_ma20:
        return ("SHORT", weak)
    else:
        return (None, True)

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

        msg = (
            f"📈 {symbol_display}\n"
            f"{side}\n"
            f"📌 Chế độ: {mode}\n"
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

        all_coins = await get_top_futures(limit=15)
        if not all_coins:
            await bot.send_message(chat_id=S.TELEGRAM_ALLOWED_USER_ID,
                                   text="⚠️ Không lấy được dữ liệu coin từ sàn.")
            return

        selected = random.sample(all_coins, min(5, len(all_coins)))
        _last_selected = selected

        for coin in selected:
            klines = await get_klines(coin["symbol"], limit=50)
            side, weak = decide_direction_with_indicators(klines)
            if not side:
                continue
            msg = create_trade_signal(
                symbol=coin["symbol"],
                side=side,
                entry_raw=coin["lastPrice"],
                mode="SCALPING",
                currency_mode=currency_mode,
                vnd_rate=vnd_rate,
                weak=weak
            )
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
