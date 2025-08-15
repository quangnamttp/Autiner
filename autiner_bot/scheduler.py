# autiner_bot/scheduler.py
import asyncio
import pytz
import traceback
from datetime import time
from telegram import Bot

from autiner_bot.settings import S
from autiner_bot.utils.state import get_state
from autiner_bot.utils.time_utils import get_vietnam_time
from autiner_bot.data_sources.mexc import get_top_moving_coins
from autiner_bot.data_sources.exchange import get_usdt_vnd_rate
from autiner_bot.jobs.daily_reports import job_morning_message, job_evening_summary

bot = Bot(token=S.TELEGRAM_BOT_TOKEN)


# Format giá
def _trim_trailing_zeros(s: str) -> str:
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s

def format_price_usd(value: float) -> str:
    if value >= 1:
        s = f"{value:,.8f}".replace(",", ".")
        return _trim_trailing_zeros(s)
    else:
        s = f"{value:.8f}"
        return _trim_trailing_zeros(s)

def format_price_vnd(value: float, vnd_rate: float) -> str:
    vnd_value = value * vnd_rate
    if vnd_value >= 1000:
        s = f"{vnd_value:,.2f}".replace(",", ".")
    else:
        s = f"{vnd_value:.4f}"
    return _trim_trailing_zeros(s) + " VND"


# Tạo tín hiệu
def create_trade_signal(symbol: str, last_price: float, change_pct: float):
    tp_pct = 0.5 if change_pct > 0 else -0.5
    sl_pct = -0.3 if change_pct > 0 else 0.3

    tp_price = last_price * (1 + tp_pct / 100.0)
    sl_price = last_price * (1 + sl_pct / 100.0)

    strength = max(1, min(int(abs(change_pct) * 10), 100))

    return {
        "symbol": symbol,
        "side": "LONG" if change_pct > 0 else "SHORT",
        "orderType": "MARKET",
        "entry": last_price,
        "tp": tp_price,
        "sl": sl_price,
        "strength": strength,
        "reason": f"Biến động {change_pct:.2f}% trong 15 phút"
    }


# Gửi tín hiệu
async def job_trade_signals():
    try:
        state = get_state()
        if not state["is_on"]:
            return

        moving_task = asyncio.create_task(get_top_moving_coins(limit=5))
        rate_task = asyncio.create_task(get_usdt_vnd_rate())
        moving_coins, vnd_rate = await asyncio.gather(moving_task, rate_task)

        if not vnd_rate or vnd_rate <= 0:
            await bot.send_message(
                chat_id=S.TELEGRAM_ALLOWED_USER_ID,
                text="⚠️ Không lấy được tỷ giá USDT/VND."
            )
            return

        for c in moving_coins:
            change_pct = float(c.get("change_pct", 0.0))
            last_price = float(c.get("lastPrice", 0.0))

            sig = create_trade_signal(c["symbol"], last_price, change_pct)

            entry_usd = format_price_usd(sig['entry'])
            entry_vnd = format_price_vnd(sig['entry'], vnd_rate)
            tp_usd = format_price_usd(sig['tp'])
            tp_vnd = format_price_vnd(sig['tp'], vnd_rate)
            sl_usd = format_price_usd(sig['sl'])
            sl_vnd = format_price_vnd(sig['sl'], vnd_rate)

            symbol_display = sig['symbol'].replace("_USDT", "/USD")
            side_icon = "🟩 LONG" if sig["side"] == "LONG" else "🟥 SHORT"
            highlight = "⭐ " if sig["strength"] >= 70 else ""

            msg = (
                f"{highlight}📈 {symbol_display} — {side_icon}\n\n"
                f"🔹 Kiểu vào lệnh: MARKET\n"
                f"💰 Entry: {entry_usd} USD | {entry_vnd}\n"
                f"🎯 TP: {tp_usd} USD | {tp_vnd}\n"
                f"🛡️ SL: {sl_usd} USD | {sl_vnd}\n"
                f"📊 Độ mạnh: {sig['strength']}%\n"
                f"📌 Lý do: {sig['reason']}\n"
                f"🕒 Thời gian: {get_vietnam_time().strftime('%H:%M %d/%m/%Y')}"
            )

            await bot.send_message(chat_id=S.TELEGRAM_ALLOWED_USER_ID, text=msg)

    except Exception as e:
        print(f"[ERROR] job_trade_signals: {e}")
        print(traceback.format_exc())


# Đăng ký job sáng & tối
def register_daily_jobs(job_queue):
    tz = pytz.timezone("Asia/Ho_Chi_Minh")
    job_queue.run_daily(job_morning_message, time=time(hour=6, minute=0, tzinfo=tz))
    job_queue.run_daily(job_evening_summary, time=time(hour=22, minute=0, tzinfo=tz))
