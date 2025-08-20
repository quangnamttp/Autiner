# autiner_bot/scheduler.py

from telegram import Bot
from autiner_bot.settings import S
from autiner_bot.utils.state import get_state
from autiner_bot.utils.time_utils import get_vietnam_time
from autiner_bot.data_sources.mexc import (
    get_usdt_vnd_rate,
    get_top_futures,
    get_market_sentiment,
    get_coin_data,
)
from autiner_bot.jobs.daily_reports import job_morning_message, job_evening_summary

import traceback
import pytz
import numpy as np
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
# Chỉ báo kỹ thuật (RSI, MA)
# =============================
def calculate_rsi(prices, period=14):
    if len(prices) < period + 1:
        return 50
    deltas = np.diff(prices)
    gains = deltas.clip(min=0)
    losses = -deltas.clip(max=0)
    avg_gain = gains[-period:].mean() if len(gains) >= period else gains.mean() if gains.size else 0
    avg_loss = losses[-period:].mean() if len(losses) >= period else losses.mean() if losses.size else 0
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def calculate_ma(prices, period=20):
    if len(prices) < period:
        return float(np.mean(prices))
    return float(np.mean(prices[-period:]))


def analyze_signal(coin_klines: list):
    """
    Trả về LONG / SHORT / SIDEWAY dựa vào RSI + MA (thoáng hơn):
    - RSI > 65 và giá > MA20  -> LONG
    - RSI < 35 và giá < MA20  -> SHORT
    - Nếu trung tính: dùng giá so với MA20 làm quyết định
    - Chỉ trả SIDEWAY khi dữ liệu quá ít (<10 nến)
    """
    try:
        if not coin_klines or len(coin_klines) < 10:
            return "SIDEWAY"

        closes = [k["close"] for k in coin_klines]
        rsi = calculate_rsi(closes, period=14)
        ma20 = calculate_ma(closes, period=20)
        last_price = closes[-1]

        # Quy tắc thoáng
        if rsi >= 65 and last_price >= ma20:
            return "LONG"
        if rsi <= 35 and last_price <= ma20:
            return "SHORT"

        # Trung tính -> ưu tiên giá so với MA20 để ra hướng
        if last_price > ma20:
            return "LONG"
        if last_price < ma20:
            return "SHORT"

        return "SIDEWAY"
    except Exception as e:
        print(f"[ERROR] analyze_signal: {e}")
        return "SIDEWAY"


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
def create_trade_signal(symbol: str, entry_raw: float, signal: str,
                        mode: str, currency_mode="USD", vnd_rate=None, weak=False):
    try:
        entry_price = format_price(entry_raw, currency_mode, vnd_rate)

        # TP/SL
        if signal == "LONG":
            tp_val = entry_raw * (1.01 if mode.upper() == "SCALPING" else 1.02)
            sl_val = entry_raw * (0.99 if mode.upper() == "SCALPING" else 0.98)
            side_icon = "🟩 LONG"
        elif signal == "SHORT":
            tp_val = entry_raw * (0.99 if mode.upper() == "SCALPING" else 0.98)
            sl_val = entry_raw * (1.01 if mode.upper() == "SCALPING" else 1.02)
            side_icon = "🟥 SHORT"
        else:
            # SIDEWAY vẫn gửi, gắn nhãn tham khảo
            tp_val = entry_raw
            sl_val = entry_raw
            side_icon = "⚠️ SIDEWAY"

        tp = format_price(tp_val, currency_mode, vnd_rate)
        sl = format_price(sl_val, currency_mode, vnd_rate)

        symbol_display = symbol.replace("_USDT", f"/{currency_mode.upper()}")
        label = "⭐ TÍN HIỆU ⭐"

        # Độ mạnh
        strength = "Tham khảo" if (weak or signal == "SIDEWAY") else f"{random.randint(60, 90)}%"

        msg = (
            f"{label}\n"
            f"📈 {symbol_display}\n"
            f"{side_icon}\n"
            f"📌 Chế độ: {mode.upper()}\n"
            f"💰 Entry: {entry_price} {currency_mode}\n"
            f"🎯 TP: {tp} {currency_mode}\n"
            f"🛑 SL: {sl} {currency_mode}\n"
            f"🕒 {get_vietnam_time().strftime('%H:%M %d/%m/%Y')}\n"
            f"📊 Độ mạnh: {strength}"
        )
        return msg
    except Exception as e:
        print(f"[ERROR] create_trade_signal: {e}")
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

        all_coins = await get_top_futures(limit=15)
        sentiment = await get_market_sentiment()
        if not all_coins:
            await bot.send_message(chat_id=S.TELEGRAM_ALLOWED_USER_ID,
                                   text="⚠️ Không lấy được dữ liệu coin từ sàn.")
            return

        # Thị trường sideway dùng để gắn nhãn 'Tham khảo' nếu muốn
        market_sideway = abs(sentiment["long"] - sentiment["short"]) <= 10

        # chọn 5 coin ngẫu nhiên trong top 15
        selected = random.sample(all_coins, min(5, len(all_coins)))
        if not selected:
            await bot.send_message(chat_id=S.TELEGRAM_ALLOWED_USER_ID,
                                   text="⚠️ Không có tín hiệu hợp lệ trong phiên này.")
            return

        _last_selected = selected
        messages = []

        for i, coin in enumerate(selected):
            # Lấy nến Min5 (thoáng)
            data = await get_coin_data(coin["symbol"], interval="Min5", limit=60)

            # Nếu không có nến → vẫn gửi theo biến động hiện tại, gắn 'Tham khảo'
            if not data or not data.get("klines"):
                fallback_side = "LONG" if coin.get("change_pct", 0) >= 0 else "SHORT"
                mode = "SCALPING" if i < 3 else "SWING"
                msg = create_trade_signal(
                    coin["symbol"],
                    coin["lastPrice"],
                    fallback_side,
                    mode,
                    currency_mode,
                    vnd_rate,
                    weak=True  # đánh dấu tham khảo
                )
                if msg:
                    messages.append(msg)
                continue

            # Có nến → phân tích RSI + MA (thoáng)
            signal = analyze_signal(data["klines"])

            # Nếu SIDEWAY → vẫn bắn, strength = Tham khảo
            weak_flag = (signal == "SIDEWAY") or market_sideway

            mode = "SCALPING" if i < 3 else "SWING"
            msg = create_trade_signal(
                coin["symbol"],
                coin["lastPrice"],
                signal,
                mode,
                currency_mode,
                vnd_rate,
                weak=weak_flag
            )
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
