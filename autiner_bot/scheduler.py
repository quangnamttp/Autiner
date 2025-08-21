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
# Chỉ báo kỹ thuật: RSI / SMA / Bollinger / Volume
# =============================
def rsi(values, period=14):
    if len(values) < period + 1:
        return 50.0
    deltas = np.diff(values)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    avg_gain = gains[-period:].mean() if len(gains) >= period else gains.mean()
    avg_loss = losses[-period:].mean() if len(losses) >= period else losses.mean()
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def sma(values, period=20):
    if len(values) < period:
        return float(np.mean(values))
    return float(np.mean(values[-period:]))


def stddev(values, period=20):
    if len(values) < period:
        return float(np.std(values))
    return float(np.std(values[-period:], ddof=0))


def analyze_signal_with_indicators(klines: list):
    """
    Trả về (signal, strength_percent_or_text)
    signal ∈ {"LONG","SHORT","SIDEWAY"}
    strength: "Tham khảo" hoặc "NN%"
    """
    try:
        if not klines or len(klines) < 20:
            return "SIDEWAY", "Tham khảo"

        closes = [k["close"] for k in klines]
        vols   = [k["volume"] for k in klines]

        last_price = float(closes[-1])
        rsi14 = rsi(closes, 14)
        ma20  = sma(closes, 20)
        ma50  = sma(closes, 50) if len(closes) >= 50 else sma(closes, max(20, len(closes)//2))

        dev   = stddev(closes, 20)
        bb_mid = ma20
        bb_up  = ma20 + 2 * dev
        bb_lo  = ma20 - 2 * dev

        vol_avg20 = np.mean(vols[-20:]) if len(vols) >= 20 else np.mean(vols)
        vol_spike = vols[-1] >= 1.2 * vol_avg20  # spike khá thoáng

        # Nếu giá rất sát MA20 → sideway
        if ma20 > 0 and abs(last_price - ma20) / ma20 < 0.001:
            return "SIDEWAY", "Tham khảo"

        score = 0
        # MA alignment
        if last_price > ma20:
            score += 1
        if ma20 > ma50:
            score += 1
        # RSI bias
        if rsi14 > 55:
            score += 1
        if rsi14 < 45:
            score -= 1
        # Bollinger position
        if last_price > bb_mid:
            score += 1
        else:
            score -= 1
        # Volume spike làm chất xúc tác (cộng/khấu tùy hướng)
        if vol_spike:
            score += 1 if last_price > ma20 else -1

        # Quyết định hướng & độ mạnh
        # Ngưỡng thoáng: score >= 2 → LONG mạnh ; score <= -2 → SHORT mạnh
        if score >= 2:
            # tinh % strength (70-90) dựa theo số điều kiện khớp
            matches = 0
            matches += 1 if last_price > ma20 else 0
            matches += 1 if ma20 > ma50 else 0
            matches += 1 if rsi14 > 55 else 0
            matches += 1 if last_price > bb_mid else 0
            matches += 1 if vol_spike else 0
            strength = str(min(90, 65 + matches * 5)) + "%"
            return "LONG", strength

        if score <= -2:
            matches = 0
            matches += 1 if last_price < ma20 else 0
            matches += 1 if ma20 < ma50 else 0
            matches += 1 if rsi14 < 45 else 0
            matches += 1 if last_price < bb_mid else 0
            matches += 1 if vol_spike else 0
            strength = str(min(90, 65 + matches * 5)) + "%"
            return "SHORT", strength

        # Không mạnh: hướng theo giá so với MA20, nhưng đánh dấu tham khảo khi rất sát BB mid
        if last_price > ma20:
            # nếu rất gần bb_mid → tham khảo
            if abs(last_price - bb_mid) / (bb_up - bb_lo + 1e-9) < 0.05:
                return "LONG", "Tham khảo"
            return "LONG", "70%"
        elif last_price < ma20:
            if abs(last_price - bb_mid) / (bb_up - bb_lo + 1e-9) < 0.05:
                return "SHORT", "Tham khảo"
            return "SHORT", "70%"

        return "SIDEWAY", "Tham khảo"

    except Exception:
        return "SIDEWAY", "Tham khảo"


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
def create_trade_signal(symbol: str, entry_raw: float, signal: str, strength_text: str,
                        mode: str, currency_mode="USD", vnd_rate=None):
    try:
        entry_price = format_price(entry_raw, currency_mode, vnd_rate)

        # TP/SL (scalping 1%, swing 2%)
        if signal == "LONG":
            tp_val = entry_raw * (1.01 if mode.upper() == "SCALPING" else 1.02)
            sl_val = entry_raw * (0.99 if mode.upper() == "SCALPING" else 0.98)
            side_icon = "🟩 LONG"
        elif signal == "SHORT":
            tp_val = entry_raw * (0.99 if mode.upper() == "SCALPING" else 0.98)
            sl_val = entry_raw * (1.01 if mode.upper() == "SCALPING" else 1.02)
            side_icon = "🟥 SHORT"
        else:
            # SIDEWAY: vẫn cho số để ai thích ăn rung
            tp_val = entry_raw
            sl_val = entry_raw
            side_icon = "⚠️ SIDEWAY"

        tp = format_price(tp_val, currency_mode, vnd_rate)
        sl = format_price(sl_val, currency_mode, vnd_rate)
        symbol_display = symbol.replace("_USDT", f"/{currency_mode.upper()}")

        # Gọn gàng, không có tiêu đề ⭐
        msg = (
            f"📈 {symbol_display}\n"
            f"{side_icon}\n"
            f"📌 Chế độ: {mode.upper()}\n"
            f"💰 Entry: {entry_price} {currency_mode}\n"
            f"🎯 TP: {tp} {currency_mode}\n"
            f"🛑 SL: {sl} {currency_mode}\n"
            f"📊 Độ mạnh: {strength_text}\n"
            f"🕒 {get_vietnam_time().strftime('%H:%M %d/%m/%Y')}"
        )
        return msg
    except Exception as e:
        print(f"[ERROR] create_trade_signal: {e}")
        return None


# =============================
# Gửi tín hiệu giao dịch (luôn cố đủ 5 tín hiệu)
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

        coins = await get_top_futures(limit=15)
        _ = await get_market_sentiment()  # giữ nếu nơi khác dùng
        if not coins:
            await bot.send_message(chat_id=S.TELEGRAM_ALLOWED_USER_ID,
                                   text="⚠️ Không lấy được dữ liệu coin từ sàn.")
            return

        # thử nhiều coin để đảm bảo đủ 5 tín hiệu
        pool = coins[:]  # đã là top theo volume
        random.shuffle(pool)

        messages = []
        tried = 0
        for coin in pool:
            if len(messages) >= 5:
                break
            tried += 1
            # lấy nến thật – ưu tiên Min1; thiếu thì Min5 (đều là dữ liệu thật)
            data = await get_coin_data(coin["symbol"], interval="Min1", limit=120)
            if (not data) or (not data.get("klines")):
                data = await get_coin_data(coin["symbol"], interval="Min5", limit=120)
                if (not data) or (not data.get("klines")):
                    continue

            signal, strength_text = analyze_signal_with_indicators(data["klines"])
            # tất cả 5 lệnh đều SCALPING theo yêu cầu
            msg = create_trade_signal(
                coin["symbol"],
                coin["lastPrice"],
                signal,
                strength_text,
                mode="SCALPING",
                currency_mode=currency_mode,
                vnd_rate=vnd_rate,
            )
            if msg:
                messages.append(msg)

        # Nếu vì lý do nào đó <5, vẫn gửi những gì có
        if messages:
            for m in messages:
                await bot.send_message(chat_id=S.TELEGRAM_ALLOWED_USER_ID, text=m)
        else:
            # cực đoan: nếu không kiếm được nến nào, gửi 1 dòng cảnh báo
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
