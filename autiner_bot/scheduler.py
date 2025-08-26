from telegram import Bot
from autiner_bot.settings import S
from autiner_bot.utils.state import get_state
from autiner_bot.utils.time_utils import get_vietnam_time
from autiner_bot.data_sources.mexc import (
    get_usdt_vnd_rate,
    get_top_futures,
)
from autiner_bot.jobs.daily_reports import job_morning_message, job_evening_summary

import traceback
import pytz
from datetime import time

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
            return f"{value:,.0f}".replace(",", ".")
        else:
            s = f"{value:.6f}".rstrip("0").rstrip(".")
            if float(s) >= 1:
                if "." in s:
                    int_part, dec_part = s.split(".")
                    int_part = f"{int(int_part):,}".replace(",", ".")
                    s = f"{int_part}.{dec_part}" if dec_part else int_part
                else:
                    s = f"{int(s):,}".replace(",", ".")
            return s
    except Exception:
        return str(value)


# =============================
# Notice trước khi ra tín hiệu
# =============================
async def job_trade_signals_notice(_=None):
    try:
        state = get_state()
        if not state["is_on"]:
            return
        msg = "⏳ 1 phút nữa sẽ có tín hiệu giao dịch, chuẩn bị sẵn sàng!"
        await bot.send_message(chat_id=S.TELEGRAM_ALLOWED_USER_ID, text=msg)
    except Exception as e:
        print(f"[ERROR] job_trade_signals_notice: {e}")


# =============================
# Tạo tín hiệu giao dịch
# =============================
def create_trade_signal(symbol, side, entry_raw,
                        mode="Scalping", currency_mode="USD",
                        vnd_rate=None):
    try:
        entry_price = format_price(entry_raw, currency_mode, vnd_rate)

        if side == "LONG":
            tp_val = entry_raw * (1.01 if mode == "Scalping" else 1.02)
            sl_val = entry_raw * (0.99 if mode == "Scalping" else 0.98)
        else:  # SHORT
            tp_val = entry_raw * (0.99 if mode == "Scalping" else 0.98)
            sl_val = entry_raw * (1.01 if mode == "Scalping" else 1.02)

        tp = format_price(tp_val, currency_mode, vnd_rate)
        sl = format_price(sl_val, currency_mode, vnd_rate)

        symbol_display = symbol.replace("_USDT", f"/{currency_mode.upper()}")

        msg = (
            f"📈 {symbol_display} — {'🟢 LONG' if side=='LONG' else '🟥 SHORT'}\n\n"
            f"🟢 Loại lệnh: {mode}\n"
            f"🔹 Kiểu vào lệnh: Market\n"
            f"💰 Entry: {entry_price} {currency_mode}\n"
            f"🎯 TP: {tp} {currency_mode}\n"
            f"🛡️ SL: {sl} {currency_mode}\n"
            f"📊 Độ mạnh: 100% (Theo xu hướng giá)\n"
            f"📌 Lý do: Coin đang {'tăng' if side=='LONG' else 'giảm'} theo xu hướng thị trường\n"
            f"🕒 Thời gian: {get_vietnam_time().strftime('%H:%M %d/%m/%Y')}"
        )
        return msg
    except Exception:
        return None


# =============================
# Gửi tín hiệu giao dịch (3 Scalping + 2 Swing)
# =============================
async def job_trade_signals(_=None):
    try:
        state = get_state()
        if not state["is_on"]:
            return

        currency_mode = state.get("currency_mode", "USD")
        vnd_rate = await get_usdt_vnd_rate() if currency_mode == "VND" else None

        # lấy top 20 coin từ futures
        all_coins = await get_top_futures(limit=20)
        if not all_coins:
            await bot.send_message(chat_id=S.TELEGRAM_ALLOWED_USER_ID,
                                   text="⚠️ Không lấy được dữ liệu coin từ MEXC Futures.")
            return

        # lọc xu hướng: tăng -> LONG, giảm -> SHORT
        coin_signals = []
        for coin in all_coins:
            side = "LONG" if coin["change_pct"] > 0 else "SHORT"
            coin_signals.append({
                "symbol": coin["symbol"],
                "side": side,
                "lastPrice": coin["lastPrice"]
            })

        # lấy 5 coin đầu tiên
        top5 = coin_signals[:5]

        for idx, coin in enumerate(top5):
            mode = "Scalping" if idx < 3 else "Swing"
            msg = create_trade_signal(
                symbol=coin["symbol"],
                side=coin["side"],
                entry_raw=coin["lastPrice"],
                mode=mode,
                currency_mode=currency_mode,
                vnd_rate=vnd_rate,
            )
            if idx == 0:
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

    # Daily jobs
    application.job_queue.run_daily(job_morning_message, time=time(6, 0, 0, tzinfo=tz))
    application.job_queue.run_daily(job_evening_summary, time=time(22, 0, 0, tzinfo=tz))

    # 30 phút/lần
    for h in range(6, 22):
        for m in [0, 30]:
            notice_minute = m - 1 if m > 0 else 59
            notice_hour = h if m > 0 else (h - 1 if h > 6 else 6)
            application.job_queue.run_daily(job_trade_signals_notice, time=time(notice_hour, notice_minute, 0, tzinfo=tz))
            application.job_queue.run_daily(job_trade_signals, time=time(h, m, 0, tzinfo=tz))

    print("✅ Scheduler đã setup thành công!")
