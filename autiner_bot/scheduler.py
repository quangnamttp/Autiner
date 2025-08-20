# autiner_bot/scheduler.py

from telegram import Bot
from autiner_bot.settings import S
from autiner_bot.utils.state import get_state
from autiner_bot.utils.time_utils import get_vietnam_time
from autiner_bot.data_sources.mexc import (
    get_usdt_vnd_rate,
    get_top_futures,
    get_market_sentiment,  # vẫn import nếu bạn cần ở nơi khác
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
# Chỉ báo: RSI & MA
# =============================
def calculate_rsi(prices, period=14):
    if len(prices) < period + 1:
        return 50.0
    deltas = np.diff(prices)
    gains = np.clip(deltas, 0, None)
    losses = np.clip(-deltas, 0, None)
    avg_gain = gains[-period:].mean() if len(gains) >= period else (gains.mean() if gains.size else 0.0)
    avg_loss = losses[-period:].mean() if len(losses) >= period else (losses.mean() if losses.size else 0.0)
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return float(round(100 - (100 / (1 + rs)), 2))


def sma(values, period):
    if len(values) < period:
        return float(np.mean(values)) if values else 0.0
    return float(np.mean(values[-period:]))


# =============================
# Scoring & Direction (mạnh - trade thật)
# =============================
def score_direction(klines):
    """
    Trả về: (direction, strength_score)
      - direction ∈ {"LONG","SHORT","SIDEWAY"}
      - strength_score: 0..100 (để hiển thị %; nếu SIDEWAY thì ghi 'Tham khảo' khi render)
    Logic (thoáng vừa phải nhưng 'thật'):
      - RSI (14)
      - Giá so với MA20
      - Volume burst (vol cuối / vol TB20)
      - Momentum nến gần (close[-1] vs close[-2])
    """
    try:
        if not klines or len(klines) < 20:
            return "SIDEWAY", 0.0

        closes = [k["close"] for k in klines]
        vols   = [k["volume"] for k in klines]
        last   = closes[-1]
        prev   = closes[-2]

        rsi14  = calculate_rsi(closes, 14)
        ma20   = sma(closes, 20)
        vol20  = sma(vols, 20)
        last_vol = vols[-1]
        vol_ratio = (last_vol / vol20) if vol20 > 0 else 1.0
        mom = (last - prev) / prev if prev != 0 else 0.0
        ma_gap = (last - ma20) / ma20 if ma20 != 0 else 0.0

        # Tính hai ứng viên điểm: long_score / short_score
        # Thành phần điểm (0-100):
        #  - RSI: xa khỏi 50 về phía 60-70 cho LONG, 40-30 cho SHORT
        #  - MA: cùng phía với MA20 + khoảng cách
        #  - Volume: burst > 1.0
        #  - Momentum: biến động nến cuối

        # Chuẩn hoá đóng góp
        def clamp01(x):  # 0..1
            return max(0.0, min(1.0, x))

        # LONG components
        rsi_long = clamp01((rsi14 - 55) / 20)         # >= ~60 mạnh dần
        ma_long  = clamp01(ma_gap)                    # >0 cùng phía
        mom_long = clamp01(mom * 10)                  # ~1% = 0.1 → scaled
        vol_boost = clamp01((vol_ratio - 1.0) / 1.0)  # 2x vol -> 1.0

        long_score = (
            40 * rsi_long +
            30 * ma_long +
            20 * vol_boost +
            10 * mom_long
        )

        # SHORT components
        rsi_short = clamp01((55 - rsi14) / 20)        # <= ~40 mạnh dần
        ma_short  = clamp01(-ma_gap)                  # <0 cùng phía
        mom_short = clamp01(-mom * 10)
        short_score = (
            40 * rsi_short +
            30 * ma_short +
            20 * vol_boost +
            10 * mom_short
        )

        # Chọn hướng & điểm
        if long_score < 10 and short_score < 10:
            return "SIDEWAY", max(long_score, short_score)

        if long_score >= short_score:
            return "LONG", round(long_score, 1)
        else:
            return "SHORT", round(short_score, 1)

    except Exception as e:
        print(f"[ERROR] score_direction: {e}")
        return "SIDEWAY", 0.0


# =============================
# Notice trước khi ra tín hiệu (1 phút trước)
# =============================
async def job_trade_signals_notice(_=None):
    try:
        state = get_state()
        if not state["is_on"]:
            return
        await bot.send_message(
            chat_id=S.TELEGRAM_ALLOWED_USER_ID,
            text="⏳ 1 phút nữa sẽ có tín hiệu giao dịch (5 lệnh), chuẩn bị sẵn sàng nhé!"
        )
    except Exception as e:
        print(f"[ERROR] job_trade_signals_notice: {e}")


# =============================
# Render tín hiệu
# =============================
def create_trade_signal(symbol: str, entry_raw: float, direction: str, strength_score: float,
                        mode: str, currency_mode="USD", vnd_rate=None):
    try:
        entry_price = format_price(entry_raw, currency_mode, vnd_rate)

        if direction == "LONG":
            tp_val = entry_raw * (1.01 if mode.upper() == "SCALPING" else 1.02)
            sl_val = entry_raw * (0.99 if mode.upper() == "SCALPING" else 0.98)
            side_icon = "🟩 LONG"
        elif direction == "SHORT":
            tp_val = entry_raw * (0.99 if mode.upper() == "SCALPING" else 0.98)
            sl_val = entry_raw * (1.01 if mode.upper() == "SCALPING" else 1.02)
            side_icon = "🟥 SHORT"
        else:
            tp_val = entry_raw
            sl_val = entry_raw
            side_icon = "⚠️ SIDEWAY"

        tp = format_price(tp_val, currency_mode, vnd_rate)
        sl = format_price(sl_val, currency_mode, vnd_rate)
        symbol_display = symbol.replace("_USDT", f"/{currency_mode.upper()}")

        # Strength: nếu SIDEWAY → “Tham khảo”, ngược lại hiển thị %
        strength_txt = "Tham khảo" if direction == "SIDEWAY" else f"{int(round(strength_score))}%"

        msg = (
            f"📈 {symbol_display}\n"
            f"{side_icon}\n"
            f"📌 Chế độ: {mode.upper()}\n"
            f"💰 Entry: {entry_price} {currency_mode}\n"
            f"🎯 TP: {tp} {currency_mode}\n"
            f"🛑 SL: {sl} {currency_mode}\n"
            f"📊 Độ mạnh: {strength_txt}\n"
            f"🕒 {get_vietnam_time().strftime('%H:%M %d/%m/%Y')}"
        )
        return msg
    except Exception as e:
        print(f"[ERROR] create_trade_signal: {e}")
        return None


# =============================
# Gửi tín hiệu giao dịch — mỗi giờ 5 lệnh
# =============================
async def job_trade_signals(_=None):
    global _last_selected
    try:
        state = get_state()
        if not state.get("is_on", True):
            return

        currency_mode = state.get("currency_mode", "USD")
        vnd_rate = None
        if currency_mode == "VND":
            vnd_rate = await get_usdt_vnd_rate()
            if not vnd_rate or vnd_rate <= 0:
                await bot.send_message(S.TELEGRAM_ALLOWED_USER_ID, "⚠️ Không lấy được tỷ giá USDT/VND.")
                return

        # Lấy top coin và chấm điểm tất cả → chọn top 5 mạnh nhất
        universe = await get_top_futures(limit=20)   # lấy rộng hơn để đủ 5 lệnh mạnh
        if not universe:
            await bot.send_message(S.TELEGRAM_ALLOWED_USER_ID, "⚠️ Không lấy được dữ liệu coin từ sàn.")
            return

        scored = []
        for coin in universe:
            # LẤY NẾN THẬT (Min1 -> fallback Min5 nếu Min1 rỗng)
            data = await get_coin_data(coin["symbol"], interval="Min1", limit=60)
            if (not data) or (not data.get("klines")):
                data = await get_coin_data(coin["symbol"], interval="Min5", limit=60)
                if (not data) or (not data.get("klines")):
                    continue

            direction, score = score_direction(data["klines"])

            # Ưu tiên loại bỏ SIDEWAY ở vòng chọn đầu
            scored.append({
                "symbol": coin["symbol"],
                "entry": coin["lastPrice"],
                "direction": direction,
                "score": score
            })

        if not scored:
            await bot.send_message(S.TELEGRAM_ALLOWED_USER_ID, "⚠️ Không có tín hiệu hợp lệ trong phiên này.")
            return

        # 1) Lọc tín hiệu MẠNH (không sideway) & score >= 55
        strong = [s for s in scored if s["direction"] in ("LONG", "SHORT") and s["score"] >= 55]
        strong.sort(key=lambda x: x["score"], reverse=True)

        picks = strong[:5]

        # 2) Nếu chưa đủ 5, nới tiêu chí (score >= 45)
        if len(picks) < 5:
            medium = [s for s in scored if s["direction"] in ("LONG", "SHORT") and s["score"] >= 45 and s not in picks]
            medium.sort(key=lambda x: x["score"], reverse=True)
            picks += medium[: (5 - len(picks))]

        # 3) Nếu vẫn thiếu, chấp nhận sideway (để đảm bảo đủ 5 lệnh/giờ)
        if len(picks) < 5:
            side = [s for s in scored if s["direction"] == "SIDEWAY" and s not in picks]
            # ưu tiên score cao hơn trong sideway (dù vẫn ghi 'Tham khảo')
            side.sort(key=lambda x: x["score"], reverse=True)
            picks += side[: (5 - len(picks))]

        if not picks:
            await bot.send_message(S.TELEGRAM_ALLOWED_USER_ID, "⚠️ Không có tín hiệu hợp lệ trong phiên này.")
            return

        # Render & gửi (3 SCALPING đầu, 2 SWING sau)
        _last_selected = picks
        for i, p in enumerate(picks):
            mode = "SCALPING" if i < 3 else "SWING"
            msg = create_trade_signal(
                p["symbol"], p["entry"], p["direction"], p["score"],
                mode, currency_mode, vnd_rate
            )
            if msg:
                await bot.send_message(chat_id=S.TELEGRAM_ALLOWED_USER_ID, text=msg)

    except Exception as e:
        print(f"[ERROR] job_trade_signals: {e}")
        print(traceback.format_exc())


# =============================
# Setup job — mỗi GIỜ
# =============================
def setup_jobs(application):
    tz = pytz.timezone("Asia/Ho_Chi_Minh")

    # Daily sáng / tối (giữ nguyên)
    application.job_queue.run_daily(job_morning_message, time=time(6, 0, 0, tzinfo=tz))
    application.job_queue.run_daily(job_evening_summary, time=time(22, 0, 0, tzinfo=tz))

    # TÍN HIỆU MỖI GIỜ: notice tại xx:14, tín hiệu tại xx:15
    for h in range(6, 22):  # 06:xx → 21:xx
        application.job_queue.run_daily(job_trade_signals_notice, time=time(h, 14, 0, tzinfo=tz))
        application.job_queue.run_daily(job_trade_signals,       time=time(h, 15, 0, tzinfo=tz))

    print("✅ Scheduler đã setup chế độ MỖI GIỜ (06:15 → 21:15), 5 tín hiệu/giờ.")
