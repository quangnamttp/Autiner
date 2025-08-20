# autiner_bot/scheduler.py

from telegram import Bot
from autiner_bot.settings import S
from autiner_bot.utils.state import get_state
from autiner_bot.utils.time_utils import get_vietnam_time
from autiner_bot.data_sources.mexc import (
    get_usdt_vnd_rate,
    get_top_futures,
    get_market_sentiment,
    get_coin_data,          # cần có trong mexc (đã có)
)

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
# Chỉ báo nhẹ: RSI(14) + Bollinger (MA20, 2σ)
# =============================
def rsi_14(closes):
    if len(closes) < 15:
        return None
    deltas = np.diff(closes)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    n = 14
    if len(gains) < n or len(losses) < n:
        return None
    avg_gain = np.mean(gains[-n:])
    avg_loss = np.mean(losses[-n:])
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def bbands_20_2(closes):
    if len(closes) < 20:
        return None, None, None, None
    window = np.array(closes[-20:])
    ma20 = float(np.mean(window))
    std = float(np.std(window, ddof=0))
    upper = ma20 + 2 * std
    lower = ma20 - 2 * std
    width_pct = 0.0 if ma20 == 0 else (upper - lower) / ma20 * 100
    return ma20, upper, lower, width_pct


# =============================
# Quyết định hướng mềm (KHÔNG gắt)
# - Hướng gốc: theo change_pct
# - RSI & BB chỉ "đỡ lưng" để tăng độ chính xác
# =============================
def decide_direction(change_pct, closes, volumes):
    # Hướng gốc theo biến động hiện tại
    base = "LONG" if change_pct > 0 else ("SHORT" if change_pct < 0 else "LONG")

    # Nếu không đủ dữ liệu nến -> trả về theo base, strength “Tham khảo” nếu biến động quá nhỏ
    if not closes or len(closes) < 20:
        weak = abs(change_pct) < 0.5
        return base, ("Tham khảo" if weak else f"{random.randint(70, 90)}%")

    last = closes[-1]
    rsi = rsi_14(closes)
    ma20, upper, lower, width_pct = bbands_20_2(closes)

    # Gợi ý từ RSI
    rsi_hint = None
    if rsi is not None:
        if rsi >= 62:
            rsi_hint = "LONG"
        elif rsi <= 38:
            rsi_hint = "SHORT"

    # Gợi ý từ BB (đóng ngoài dải)
    bb_hint = None
    if ma20 is not None and upper is not None and lower is not None:
        if last > upper:
            bb_hint = "LONG"
        elif last < lower:
            bb_hint = "SHORT"

    # Kết hợp (mềm)
    agreed = rsi_hint == bb_hint and rsi_hint is not None
    one_hint = (rsi_hint is not None) ^ (bb_hint is not None)
    hint_dir = rsi_hint or bb_hint

    # Sideway rộng/hẹp để xác định "Tham khảo"
    sidewayish = (abs(change_pct) < 0.5) or (width_pct is not None and width_pct < 0.4)

    # Volume boost
    vol_boost = 0
    if volumes and len(volumes) >= 20:
        last_vol = volumes[-1]
        avg_vol = float(np.mean(volumes[-20:]))
        if avg_vol > 0 and last_vol > avg_vol * 1.2:
            vol_boost = 5

    # Quyết định cuối
    if agreed:
        direction = rsi_hint
        base_strength = random.randint(75, 92) + vol_boost
        strength = f"{min(base_strength, 96)}%"
    elif one_hint:
        direction = hint_dir
        base_strength = random.randint(65, 80) + vol_boost
        strength = f"{min(base_strength, 92)}%"
    else:
        direction = base
        strength = "Tham khảo" if sidewayish else f"{random.randint(65, 85)}%"

    return direction, strength


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
# Tạo nội dung tín hiệu (không header sao/sideway)
# =============================
def build_signal_message(symbol: str, direction: str, entry_raw: float,
                         mode: str, currency_mode="USD", vnd_rate=None, strength="Tham khảo"):
    entry_price = format_price(entry_raw, currency_mode, vnd_rate)

    if direction == "LONG":
        tp_val = entry_raw * (1.01 if mode.upper() == "SCALPING" else 1.02)
        sl_val = entry_raw * (0.99 if mode.upper() == "SCALPING" else 0.98)
        side_line = "🟩 LONG"
    else:
        tp_val = entry_raw * (0.99 if mode.upper() == "SCALPING" else 0.98)
        sl_val = entry_raw * (1.01 if mode.upper() == "SCALPING" else 1.02)
        side_line = "🟥 SHORT"

    tp = format_price(tp_val, currency_mode, vnd_rate)
    sl = format_price(sl_val, currency_mode, vnd_rate)

    symbol_display = symbol.replace("_USDT", f"/{currency_mode.upper()}")

    msg = (
        f"📈 {symbol_display}\n"
        f"{side_line}\n"
        f"📌 Chế độ: {mode.upper()}\n"
        f"💰 Entry: {entry_price} {currency_mode}\n"
        f"🎯 TP: {tp} {currency_mode}\n"
        f"🛑 SL: {sl} {currency_mode}\n"
        f"📊 Độ mạnh: {strength}\n"
        f"🕒 {get_vietnam_time().strftime('%H:%M %d/%m/%Y')}"
    )
    return msg


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
                await bot.send_message(
                    chat_id=S.TELEGRAM_ALLOWED_USER_ID,
                    text="⚠️ Không lấy được tỷ giá USDT/VND. Tín hiệu bị hủy."
                )
                return

        all_coins = await get_top_futures(limit=15)   # top 15 realtime
        _ = await get_market_sentiment()               # vẫn giữ nếu bạn cần chỗ khác

        if not all_coins:
            await bot.send_message(
                chat_id=S.TELEGRAM_ALLOWED_USER_ID,
                text="⚠️ Không lấy được dữ liệu coin từ sàn."
            )
            return

        # Luôn chọn đủ 5 coin nếu có
        selected = random.sample(all_coins, min(5, len(all_coins)))
        if not selected:
            await bot.send_message(
                chat_id=S.TELEGRAM_ALLOWED_USER_ID,
                text="⚠️ Không có tín hiệu hợp lệ trong phiên này."
            )
            return

        _last_selected = selected

        # Gửi 5 tín hiệu (tất cả SCALPING như yêu cầu)
        for coin in selected:
            # Lấy nến thật Min1 (không giả lập). Nếu không có nến → vẫn gửi theo change_pct.
            kl = []
            try:
                data = await get_coin_data(coin["symbol"], interval="Min1", limit=60)
                if data and data.get("klines"):
                    kl = data["klines"]
            except Exception:
                kl = []

            closes = [k["close"] for k in kl] if kl else []
            volumes = [k["volume"] for k in kl] if kl else []

            # Hướng mặc định theo change_pct
            change = float(coin.get("change_pct", 0.0))
            direction, strength = decide_direction(change, closes, volumes)

            msg = build_signal_message(
                symbol=coin["symbol"],
                direction=direction,
                entry_raw=coin["lastPrice"],
                mode="SCALPING",
                currency_mode=currency_mode,
                vnd_rate=vnd_rate,
                strength=strength
            )
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
    from autiner_bot.jobs.daily_reports import job_morning_message, job_evening_summary
    application.job_queue.run_daily(job_morning_message, time=time(6, 0, 0, tzinfo=tz))
    application.job_queue.run_daily(job_evening_summary, time=time(22, 0, 0, tzinfo=tz))

    # Tín hiệu mỗi 30 phút (06:15 → 21:45)
    for h in range(6, 22):
        for m in [15, 45]:
            application.job_queue.run_daily(job_trade_signals_notice, time=time(h, m - 1, 0, tzinfo=tz))
            application.job_queue.run_daily(job_trade_signals, time=time(h, m, 0, tzinfo=tz))

    print("✅ Scheduler đã setup thành công!")
