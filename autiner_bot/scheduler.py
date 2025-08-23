from telegram import Bot
from autiner_bot.settings import S
from autiner_bot.utils.state import get_state
from autiner_bot.utils.time_utils import get_vietnam_time
from autiner_bot.data_sources.mexc import (
    get_usdt_vnd_rate,
    get_top_futures,
    get_kline,
    get_funding_rate,
    get_orderbook,
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
# EMA / RSI / MACD
# =============================
def ema(values, period):
    if not values or len(values) < period:
        return sum(values) / len(values) if values else 0
    k = 2 / (period + 1)
    ema_val = values[0]
    for v in values[1:]:
        ema_val = v * k + ema_val * (1 - k)
    return ema_val


def rsi(values, period=14):
    if len(values) < period + 1:
        return 50
    deltas = np.diff(values)
    ups = deltas[deltas > 0].sum() / period
    downs = -deltas[deltas < 0].sum() / period
    rs = ups / downs if downs != 0 else 0
    return 100 - (100 / (1 + rs))


def macd(values, fast=12, slow=26, signal=9):
    if len(values) < slow:
        return 0, 0
    ema_fast = ema(values, fast)
    ema_slow = ema(values, slow)
    macd_val = ema_fast - ema_slow
    signal_val = ema(values, signal)
    return macd_val, signal_val


# =============================
# Quyết định xu hướng
# =============================
def decide_direction(klines: list, funding: float, orderbook: dict):
    if not klines or len(klines) < 30:
        return ("LONG", True, "Không đủ dữ liệu", 0)

    closes = [k["close"] for k in klines]

    ema6 = ema(closes, 6)
    ema12 = ema(closes, 12)
    rsi_val = rsi(closes, 14)
    macd_val, macd_signal = macd(closes)

    last = closes[-1]
    diff = abs(ema6 - ema12) / last * 100
    reason_parts = [
        f"EMA6={ema6:.2f}, EMA12={ema12:.2f}",
        f"RSI={rsi_val:.1f}",
        f"MACD={macd_val:.4f}, Sig={macd_signal:.4f}"
    ]

    # EMA trend
    if ema6 > ema12:
        trend = "LONG"
    elif ema6 < ema12:
        trend = "SHORT"
    else:
        return ("LONG", True, "Không rõ xu hướng", diff)

    weak = False

    # RSI filter
    if trend == "LONG" and rsi_val > 70:
        reason_parts.append("RSI quá mua")
        weak = True
    if trend == "SHORT" and rsi_val < 30:
        reason_parts.append("RSI quá bán")
        weak = True

    # MACD confirm
    if trend == "LONG" and macd_val < macd_signal:
        reason_parts.append("MACD chưa xác nhận")
        weak = True
    if trend == "SHORT" and macd_val > macd_signal:
        reason_parts.append("MACD chưa xác nhận")
        weak = True

    # Funding bias
    if funding > 0.1:
        reason_parts.append("Funding + (crowded LONG)")
    elif funding < -0.1:
        reason_parts.append("Funding - (crowded SHORT)")

    # Orderbook check
    if orderbook:
        bids = orderbook.get("bids", 1)
        asks = orderbook.get("asks", 1)
        if bids / asks > 1.1:
            reason_parts.append("Áp lực mua")
        elif asks / bids > 1.1:
            reason_parts.append("Áp lực bán")

    return (trend, weak, ", ".join(reason_parts), diff)


# =============================
# Notice trước khi ra tín hiệu (chỉ tính top5)
# =============================
async def job_trade_signals_notice(_=None):
    try:
        state = get_state()
        if not state["is_on"]:
            return

        all_coins = await get_top_futures(limit=15)
        if not all_coins:
            return

        coin_signals = []
        for coin in all_coins:
            klines = await get_kline(coin["symbol"], limit=30, interval="Min15")
            funding = await get_funding_rate(coin["symbol"])
            orderbook = await get_orderbook(coin["symbol"])
            side, weak, reason, diff = decide_direction(klines, funding, orderbook)
            coin_signals.append({
                "symbol": coin["symbol"],
                "weak": weak,
                "strength": diff
            })

        # lấy top5 giống lúc trade
        coin_signals.sort(key=lambda x: x["strength"], reverse=True)
        top5 = coin_signals[:5]

        strong_count = sum(1 for c in top5 if not c["weak"])
        weak_count = sum(1 for c in top5 if c["weak"])

        msg = (
            f"⏳ 1 phút nữa sẽ có tín hiệu giao dịch!\n"
            f"📊 Dự kiến: {strong_count} tín hiệu mạnh, {weak_count} tín hiệu tham khảo."
        )
        await bot.send_message(chat_id=S.TELEGRAM_ALLOWED_USER_ID, text=msg)
    except Exception as e:
        print(f"[ERROR] job_trade_signals_notice: {e}")


# =============================
# Tạo tín hiệu giao dịch
# =============================
def create_trade_signal(symbol, side, entry_raw,
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
            klines = await get_kline(coin["symbol"], limit=30, interval="Min15")
            funding = await get_funding_rate(coin["symbol"])
            orderbook = await get_orderbook(coin["symbol"])
            side, weak, reason, diff = decide_direction(klines, funding, orderbook)

            coin_signals.append({
                "symbol": coin["symbol"],
                "side": side,
                "reason": reason,
                "strength": diff,
                "lastPrice": coin["lastPrice"],
                "weak": weak
            })

        if not coin_signals:
            await bot.send_message(chat_id=S.TELEGRAM_ALLOWED_USER_ID,
                                   text="⚠️ Không có coin nào có tín hiệu.")
            return

        # sắp xếp theo strength
        coin_signals.sort(key=lambda x: x["strength"], reverse=True)
        top5 = coin_signals[:5]

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
            if idx == 0 and not coin["weak"]:
                msg = msg.replace("📈", "📈⭐", 1)
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
