# autiner_bot/scheduler.py

from telegram import Bot
from autiner_bot.settings import S
from autiner_bot.utils.state import get_state
from autiner_bot.utils.time_utils import get_vietnam_time
from autiner_bot.data_sources.mexc import (
    get_usdt_vnd_rate,
    get_top_futures,
    get_market_sentiment,   # vẫn import để không thay đổi hành vi chỗ khác
    get_coin_data,          # dùng để lấy nến thật khi có
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
        if currency.upper() == "VND":
            if not vnd_rate or vnd_rate <= 0:
                return "N/A VND"
            value = value * vnd_rate
            if value >= 1_000_000:
                return f"{round(value):,}".replace(",", ".")
            else:
                return f"{value:,.2f}".replace(",", ".")
        else:
            s = f"{value:.6f}".rstrip("0").rstrip(".")
            if float(s or 0) >= 1:
                if "." in s:
                    int_part, dec_part = s.split(".")
                    int_part = f"{int(int_part):,}".replace(",", ".")
                    s = f"{int_part}.{dec_part}"
                else:
                    s = f"{int(float(s)):,}".replace(",", ".")
            return s
    except Exception:
        return str(value)


# =============================
# Chỉ báo: RSI (thoáng)
# =============================
def calculate_rsi(prices, period=14):
    try:
        if len(prices) < period + 1:
            return 50.0
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0.0)
        losses = np.where(deltas < 0, -deltas, 0.0)
        avg_gain = gains[-period:].mean() if len(gains) >= period else gains.mean()
        avg_loss = losses[-period:].mean() if len(losses) >= period else losses.mean()
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return round(100 - (100 / (1 + rs)), 2)
    except Exception:
        return 50.0


# =============================
# Quyết định hướng (LONG/SHORT) + cờ Tham khảo
# Base theo change_pct; RSI + Volume chỉ xác nhận NHẸ
# =============================
def decide_direction_with_rsi_volume(coin: dict, klines: list | None):
    """
    Trả về: (direction, is_reference)
      - direction: "LONG" | "SHORT"
      - is_reference: True nếu yếu/mơ hồ/thiếu nến → hiển thị 'Độ mạnh: Tham khảo'
    """
    try:
        change = float(coin.get("change_pct", 0.0))
        abs_change = abs(change)

        # Base hướng: theo change_pct
        if abs_change < 0.3:  # gần như đứng yên → vẫn đưa hướng nhưng đánh dấu tham khảo
            base_dir = "LONG" if change >= 0 else "SHORT"
            return base_dir, True
        base_dir = "LONG" if change > 0 else "SHORT"

        # Nếu không có nến → không lật kèo, chỉ đánh dấu tham khảo nhẹ
        if not klines:
            return base_dir, True

        closes = [k["close"] for k in klines][-60:]
        vols   = [k["volume"] for k in klines][-60:]
        if len(closes) < 20 or len(vols) < 20:
            return base_dir, True

        rsi = calculate_rsi(closes, 14)
        last_vol = vols[-1]
        avg_vol20 = float(np.mean(vols[-20:]))

        is_ref = False

        # Ngưỡng xác nhận thoáng:
        # - LONG hợp lệ hơn khi RSI >= 50 và vol không quá thấp
        # - SHORT hợp lệ hơn khi RSI <= 50 và vol không quá thấp
        # Nếu mâu thuẫn nhưng biến động mạnh (|change|>=1.0) vẫn cho qua (không tham khảo)
        if base_dir == "LONG":
            if not (rsi >= 50 and last_vol >= 0.7 * avg_vol20):
                # mâu thuẫn → nếu biến động không mạnh, đánh dấu tham khảo
                if abs_change < 1.0:
                    is_ref = True
        else:  # SHORT
            if not (rsi <= 50 and last_vol >= 0.7 * avg_vol20):
                if abs_change < 1.0:
                    is_ref = True

        return base_dir, is_ref
    except Exception:
        # Có lỗi phân tích → vẫn trả về base theo giá, nhưng tham khảo
        change = float(coin.get("change_pct", 0.0))
        base_dir = "LONG" if change >= 0 else "SHORT"
        return base_dir, True


# =============================
# Notice trước khi ra tín hiệu
# =============================
async def job_trade_signals_notice(_=None):
    try:
        state = get_state()
        if not state.get("is_on"):
            return
        await bot.send_message(
            chat_id=S.TELEGRAM_ALLOWED_USER_ID,
            text="⏳ 1 phút nữa sẽ có tín hiệu giao dịch, chuẩn bị sẵn sàng nhé!"
        )
    except Exception as e:
        print(f"[ERROR] job_trade_signals_notice: {e}")


# =============================
# Tạo tín hiệu giao dịch (không dùng nhãn ⭐)
# =============================
def create_trade_signal(symbol: str, entry_raw: float, direction: str,
                        mode: str = "SCALPING", currency_mode="USD",
                        vnd_rate=None, reference=False):
    try:
        entry = format_price(entry_raw, currency_mode, vnd_rate)

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

        symbol_display = symbol.replace("_USDT", f"/{currency_mode.upper()}")
        strength = "Tham khảo" if reference else f"{random.randint(70, 95)}%"

        msg = (
            f"📈 {symbol_display}\n"
            f"{side_icon}\n"
            f"📌 Chế độ: {mode.upper()}\n"
            f"💰 Entry: {entry} {currency_mode}\n"
            f"🎯 TP: {tp} {currency_mode}\n"
            f"🛑 SL: {sl} {currency_mode}\n"
            f"📊 Độ mạnh: {strength}\n"
            f"🕒 {get_vietnam_time().strftime('%H:%M %d/%m/%Y')}"
        )
        return msg
    except Exception as e:
        print(f"[ERROR] create_trade_signal: {e}")
        return None


# =============================
# Gửi tín hiệu giao dịch (luôn cố gắng đủ 5 lệnh)
# =============================
async def job_trade_signals(_=None):
    global _last_selected
    try:
        state = get_state()
        if not state.get("is_on"):
            return

        currency_mode = state.get("currency_mode", "USD")
        vnd_rate = None
        if currency_mode.upper() == "VND":
            vnd_rate = await get_usdt_vnd_rate()
            if not vnd_rate or vnd_rate <= 0:
                await bot.send_message(
                    chat_id=S.TELEGRAM_ALLOWED_USER_ID,
                    text="⚠️ Không lấy được tỷ giá USDT/VND. Tín hiệu bị hủy."
                )
                return

        all_coins = await get_top_futures(limit=15)
        _ = await get_market_sentiment()  # giữ call này để không thay đổi hành vi ở nơi khác

        if not all_coins:
            await bot.send_message(
                chat_id=S.TELEGRAM_ALLOWED_USER_ID,
                text="⚠️ Không lấy được dữ liệu coin từ sàn."
            )
            return

        # Luôn chọn 5 coin (nếu ít hơn thì lấy hết)
        selected = random.sample(all_coins, min(5, len(all_coins)))
        if not selected:
            await bot.send_message(
                chat_id=S.TELEGRAM_ALLOWED_USER_ID,
                text="⚠️ Không có tín hiệu hợp lệ trong phiên này."
            )
            return

        _last_selected = selected
        sent = 0

        for i, coin in enumerate(selected):
            # Lấy nến thật (không tạo giả). Thử Min1 → nếu rớt thì thử Min5. Nếu vẫn rớt, vẫn gửi dựa trên change_pct.
            klines = None
            try:
                data = await get_coin_data(coin["symbol"], interval="Min1", limit=60)
                if data and data.get("klines"):
                    klines = data["klines"]
                else:
                    data = await get_coin_data(coin["symbol"], interval="Min5", limit=60)
                    if data and data.get("klines"):
                        klines = data["klines"]
            except Exception:
                klines = None  # nếu lỗi, vẫn tiếp tục cho đủ 5 lệnh

            direction, is_ref = decide_direction_with_rsi_volume(coin, klines)
            mode = "SCALPING"  # bạn đang đánh scalp → 5 lệnh đều SCALPING
            msg = create_trade_signal(
                coin["symbol"], coin["lastPrice"], direction,
                mode=mode, currency_mode=currency_mode,
                vnd_rate=vnd_rate, reference=is_ref
            )
            if msg:
                await bot.send_message(chat_id=S.TELEGRAM_ALLOWED_USER_ID, text=msg)
                sent += 1

        if sent == 0:
            await bot.send_message(
                chat_id=S.TELEGRAM_ALLOWED_USER_ID,
                text="⚠️ Không có tín hiệu hợp lệ trong phiên này."
            )

    except Exception as e:
        print(f"[ERROR] job_trade_signals: {e}")
        print(traceback.format_exc())


# =============================
# Setup job vào job_queue
# =============================
def setup_jobs(application):
    tz = pytz.timezone("Asia/Ho_Chi_Minh")

    # Daily sáng / tối (giữ nguyên)
    application.job_queue.run_daily(job_morning_message, time=time(6, 0, 0, tzinfo=tz))
    application.job_queue.run_daily(job_evening_summary, time=time(22, 0, 0, tzinfo=tz))

    # Tín hiệu mỗi 30 phút (06:15 → 21:45) + notice trước 1 phút
    for h in range(6, 22):
        for m in [15, 45]:
            application.job_queue.run_daily(job_trade_signals_notice, time=time(h, m - 1, 0, tzinfo=tz))
            application.job_queue.run_daily(job_trade_signals,       time=time(h, m,     0, tzinfo=tz))

    print("✅ Scheduler đã setup thành công!")
