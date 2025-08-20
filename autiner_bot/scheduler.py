# autiner_bot/scheduler.py

from telegram import Bot
from autiner_bot.settings import S
from autiner_bot.utils.state import get_state
from autiner_bot.utils.time_utils import get_vietnam_time
from autiner_bot.data_sources.mexc import (
    get_usdt_vnd_rate,
    get_top_futures,
    get_market_sentiment,   # vẫn import nếu nơi khác cần
    get_coin_data,          # dùng để lấy nến thật
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
# Chỉ báo (RSI, MA, Volume)
# =============================
def calculate_rsi(prices, period=14):
    if len(prices) < period + 1:
        return 50.0
    deltas = np.diff(prices)
    gains = np.clip(deltas, a_min=0, a_max=None)
    losses = -np.clip(deltas, a_max=0, a_min=None)
    avg_gain = np.mean(gains[-period:]) if len(gains) >= period else np.mean(gains)
    avg_loss = np.mean(losses[-period:]) if len(losses) >= period else np.mean(losses)
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def sma(values, period=20):
    if len(values) < period:
        return float(np.mean(values))
    return float(np.mean(values[-period:]))


def volume_ratio(volumes, period=20):
    if len(volumes) < period + 1:
        return 1.0
    avg = float(np.mean(volumes[-period:]))
    return (volumes[-1] / avg) if avg > 0 else 1.0


# =============================
# Phân tích hướng từ Change% + MA + RSI + Volume (thoáng)
# =============================
def decide_direction_from_indicators(coin: dict, klines: list):
    """
    Trả về (direction, strength_label)
    direction: "LONG" | "SHORT"
    strength_label: "Tham khảo" | "60-95%"
    """
    try:
        closes = [k["close"] for k in klines]
        vols = [k["volume"] for k in klines]
        if len(closes) < 10:
            # thiếu nến → dựa vào change_pct cho chắc
            change = float(coin.get("change_pct", 0.0))
            direction = "LONG" if change >= 0 else "SHORT"
            return direction, "Tham khảo"

        last_price = float(closes[-1])
        ma20 = sma(closes, 20)
        rsi14 = calculate_rsi(closes, 14)
        vr = volume_ratio(vols, 20)
        change = float(coin.get("change_pct", 0.0))
        abs_change = abs(change)

        # Base hướng: từ change% và vị trí so với MA20 (ưu tiên change%)
        if abs_change >= 0.3:
            base_dir = "LONG" if change > 0 else "SHORT"
        else:
            base_dir = "LONG" if last_price >= ma20 else "SHORT"

        # Đánh giá sideway phẳng (chỉ gắn "Tham khảo" nhưng vẫn LONG/SHORT)
        flat = (abs_change < 0.2) and (ma20 > 0 and abs(last_price - ma20) / ma20 < 0.0015)

        # Điểm sức mạnh (thoáng, 60–95)
        score = 60
        if base_dir == "LONG":
            if last_price >= ma20: score += 10
            if rsi14 >= 52: score += 10
        else:
            if last_price <= ma20: score += 10
            if rsi14 <= 48: score += 10
        if vr >= 1.2: score += 5
        if abs_change >= 0.5: score += 5
        score = max(60, min(95, score))

        strength = "Tham khảo" if flat else f"{score}%"
        return base_dir, strength
    except Exception as e:
        print(f"[ERROR] decide_direction_from_indicators: {e}")
        return ("LONG" if float(coin.get("change_pct", 0.0)) >= 0 else "SHORT", "Tham khảo")


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
# Tạo tín hiệu gửi Telegram
# =============================
def build_signal_message(symbol: str, direction: str, entry_raw: float,
                         mode: str, strength: str,
                         currency_mode="USD", vnd_rate=None):
    try:
        entry_price = format_price(entry_raw, currency_mode, vnd_rate)

        # TP/SL
        if direction == "LONG":
            tp_val = entry_raw * (1.01 if mode.upper() == "SCALPING" else 1.02)
            sl_val = entry_raw * (0.99 if mode.upper() == "SCALPING" else 0.98)
            side_icon = "🟩 LONG"
        else:
            tp_val = entry_raw * (0.99 if mode.upper() == "SCALPING" else 0.98)
            sl_val = entry_raw * (1.01 if mode.upper() == "SCALPING" else 1.02)
            side_icon = "🟥 SHORT"

        tp = format_price(tp_val, currency_mode, vnd_rate)
        sl = format_price(sl_val, currency_mode, vnd_rate)

        symbol_display = symbol.replace("_USDT", f"/{currency_mode.upper()}")

        # Không gắn các nhãn ⭐/SIDEWAY ở đầu, để gọn
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
        print(f"[ERROR] build_signal_message: {e}")
        return None


# =============================
# Gửi tín hiệu giao dịch (bảo đảm cố gắng 5 lệnh)
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

        all_coins = await get_top_futures(limit=25)  # lấy rộng hơn để đảm bảo đủ 5
        if not all_coins:
            await bot.send_message(chat_id=S.TELEGRAM_ALLOWED_USER_ID,
                                   text="⚠️ Không lấy được dữ liệu coin từ sàn.")
            return

        # Xáo trộn & duyệt cho đến khi đủ 5 lệnh
        random.shuffle(all_coins)
        selected_msgs = []
        examined = 0

        for coin in all_coins:
            if len(selected_msgs) >= 5:
                break
            examined += 1

            # lấy nến thật (1m trước, thiếu thì 5m)
            data = await get_coin_data(coin["symbol"], interval="Min1", limit=120)
            if (not data) or (not data.get("klines")):
                data = await get_coin_data(coin["symbol"], interval="Min5", limit=120)
                if (not data) or (not data.get("klines")):
                    continue

            direction, strength = decide_direction_from_indicators(coin, data["klines"])
            mode = "SCALPING"  # bạn trade ngắn, giữ SCALPING cho cả 5 lệnh

            msg = build_signal_message(
                symbol=coin["symbol"],
                direction=direction,
                entry_raw=coin["lastPrice"],
                mode=mode,
                strength=strength,
                currency_mode=currency_mode,
                vnd_rate=vnd_rate
            )
            if msg:
                selected_msgs.append(msg)

        # nếu vẫn chưa đủ 5 do thiếu kline → dùng change% trực tiếp để bù cho đủ
        if len(selected_msgs) < 5:
            fillers = [c for c in all_coins if c["symbol"] not in "".join(selected_msgs)]
            for coin in fillers:
                if len(selected_msgs) >= 5:
                    break
                change = float(coin.get("change_pct", 0.0))
                direction = "LONG" if change >= 0 else "SHORT"
                strength = "Tham khảo"  # bù tín hiệu thì dán tham khảo
                msg = build_signal_message(
                    symbol=coin["symbol"],
                    direction=direction,
                    entry_raw=coin["lastPrice"],
                    mode="SCALPING",
                    strength=strength,
                    currency_mode=currency_mode,
                    vnd_rate=vnd_rate
                )
                if msg:
                    selected_msgs.append(msg)

        if selected_msgs:
            _last_selected = selected_msgs[:]
            for m in selected_msgs:
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
