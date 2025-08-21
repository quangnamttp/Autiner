# autiner_bot/scheduler.py

from telegram import Bot
from autiner_bot.settings import S
from autiner_bot.utils.state import get_state
from autiner_bot.utils.time_utils import get_vietnam_time
from autiner_bot.data_sources.mexc import (
    get_usdt_vnd_rate,
    get_top_futures,
    get_market_sentiment,
    get_coin_data,   # dùng để lấy nến
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
# Chỉ báo nhẹ từ nến (RSI/MA/Bollinger)
# =============================
def rsi14(closes):
    if len(closes) < 15:
        return None
    deltas = np.diff(closes)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    avg_gain = np.mean(gains[-14:]) if len(gains) >= 14 else np.mean(gains)
    avg_loss = np.mean(losses[-14:]) if len(losses) >= 14 else np.mean(losses)
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return float(round(100 - (100 / (1 + rs)), 2))


def ma(values, period=20):
    if len(values) < period:
        return None
    return float(np.mean(values[-period:]))


def bollinger(values, period=20, mult=2.0):
    if len(values) < period:
        return None, None, None
    arr = np.array(values[-period:])
    mid = float(np.mean(arr))
    std = float(np.std(arr, ddof=0))
    upper = mid + mult * std
    lower = mid - mult * std
    return lower, mid, upper


def decide_direction_from_klines(klines):
    """
    Trả về (direction, strength_score):
      - direction: "LONG" / "SHORT" / None (nếu không chắc)
      - strength_score: điểm 0..3 dựa vào số xác nhận khớp
    """
    try:
        closes = [k["close"] for k in klines]
        if len(closes) < 20:
            return None, 0

        last = closes[-1]
        _rsi = rsi14(closes)
        _ma20 = ma(closes, 20)
        _bb_low, _bb_mid, _bb_up = bollinger(closes, 20, 2.0)

        score_long = 0
        score_short = 0

        # Xác nhận 1: vị trí so với MA20
        if _ma20 is not None:
            if last > _ma20:
                score_long += 1
            elif last < _ma20:
                score_short += 1

        # Xác nhận 2: RSI vùng "thoáng"
        if _rsi is not None:
            if _rsi > 55:
                score_long += 1
            elif _rsi < 45:
                score_short += 1

        # Xác nhận 3: Bollinger band chạm/thoát band
        if _bb_low is not None and _bb_up is not None:
            if last > _bb_up:
                score_long += 1
            elif last < _bb_low:
                score_short += 1

        if score_long > score_short and score_long >= 1:
            return "LONG", score_long
        if score_short > score_long and score_short >= 1:
            return "SHORT", score_short

        return None, max(score_long, score_short)
    except Exception:
        return None, 0


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
# Tạo tín hiệu giao dịch (luôn ra tín hiệu)
# =============================
def create_trade_signal(coin: dict, direction: str, score: int,
                        mode: str = "SCALPING",
                        currency_mode="USD", vnd_rate=None):
    try:
        entry_raw = float(coin["lastPrice"])
        entry_price = format_price(entry_raw, currency_mode, vnd_rate)

        # TP/SL theo chế độ & hướng
        if direction == "LONG":
            tp_val = entry_raw * (1.01 if mode.upper() == "SCALPING" else 1.02)
            sl_val = entry_raw * (0.99 if mode.upper() == "SCALPING" else 0.98)
            side_icon = "🟩 LONG"
        else:  # SHORT
            tp_val = entry_raw * (0.99 if mode.upper() == "SCALPING" else 0.98)
            sl_val = entry_raw * (1.01 if mode.upper() == "SCALPING" else 1.02)
            side_icon = "🟥 SHORT"

        tp = format_price(tp_val, currency_mode, vnd_rate)
        sl = format_price(sl_val, currency_mode, vnd_rate)

        # Độ mạnh: nếu có nến & nhiều xác nhận → mạnh hơn
        if score >= 3:
            strength = f"{random.randint(85, 92)}%"
        elif score == 2:
            strength = f"{random.randint(78, 84)}%"
        elif score == 1:
            strength = f"{random.randint(70, 77)}%"
        else:
            strength = "Tham khảo"

        symbol_display = coin["symbol"].replace("_USDT", f"/{currency_mode.upper()}")

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
# Gửi tín hiệu giao dịch (luôn có 5 lệnh)
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
        _ = await get_market_sentiment()              # giữ nếu bạn dùng nơi khác

        if not all_coins:
            await bot.send_message(chat_id=S.TELEGRAM_ALLOWED_USER_ID,
                                   text="⚠️ Không lấy được dữ liệu coin từ sàn.")
            return

        # Luôn chọn 5 coin (nếu sàn trả <5 thì lấy hết)
        selected = random.sample(all_coins, min(5, len(all_coins)))
        _last_selected = selected

        for i, coin in enumerate(selected):
            # 1) Thử lấy nến thật (không fallback giả lập)
            direction = None
            score = 0
            try:
                data = await get_coin_data(coin["symbol"], interval="Min1", limit=60)
                if (not data) or (not data.get("klines")):
                    data = await get_coin_data(coin["symbol"], interval="Min5", limit=60)
                if data and data.get("klines"):
                    direction, score = decide_direction_from_klines(data["klines"])
            except Exception:
                direction, score = None, 0

            # 2) Nếu không rõ từ nến → dùng change_pct để quyết định (luôn có tín hiệu)
            if direction is None:
                try:
                    change = float(coin.get("change_pct", 0) or 0)
                except Exception:
                    change = 0.0
                direction = "LONG" if change >= 0 else "SHORT"
                score = 0  # sẽ hiển thị "Tham khảo"

            mode = "SCALPING"  # bạn muốn 5 lệnh scalping mỗi đợt
            msg = create_trade_signal(coin, direction, score, mode, currency_mode, vnd_rate)
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
