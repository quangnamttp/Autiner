from telegram import Bot
from autiner_bot.settings import S
from autiner_bot.utils.state import get_state
from autiner_bot.utils.time_utils import get_vietnam_time
from autiner_bot.data_sources.mexc import get_top_signals
from autiner_bot.data_sources.exchange import get_usdt_vnd_rate
from autiner_bot.jobs.daily_reports import job_morning_message, job_evening_summary
import asyncio
import traceback
import pytz
from datetime import time

bot = Bot(token=S.TELEGRAM_BOT_TOKEN)

def format_price(value: float, currency: str = "USD", vnd_rate: float | None = None) -> str:
    try:
        if currency == "VND":
            if not vnd_rate or vnd_rate <= 0:
                return "N/A VND"
            value = value * vnd_rate
            if value >= 1000:
                return f"{value:,.0f}".replace(",", ".") + " VND"
            elif value >= 1:
                return f"{value:.4f}".rstrip("0").rstrip(".") + " VND"
            else:
                return str(int(value)) + " VND"
        else:
            if value >= 1:
                return f"{value:,.8f}".rstrip("0").rstrip(".").replace(",", ".")
            else:
                return f"{value:.8f}".rstrip("0").rstrip(".")
    except Exception:
        return f"{value} {currency}"

# =============================
# Gửi tín hiệu giao dịch
# =============================
async def job_trade_signals():
    try:
        state = get_state()
        if not state["is_on"]:
            return

        currency_mode = state.get("currency_mode", "USD")
        vnd_rate = None

        if currency_mode == "VND":
            signals_task = asyncio.create_task(get_top_signals(limit=5))
            rate_task = asyncio.create_task(get_usdt_vnd_rate())
            signals, vnd_rate = await asyncio.gather(signals_task, rate_task)
        else:
            signals = await get_top_signals(limit=5)

        for sig in signals:
            entry_price = format_price(sig["lastPrice"], currency_mode, vnd_rate)
            symbol_display = sig["symbol"].replace("_USDT", f"/{currency_mode}")
            highlight = "⭐ " if sig["score"] >= 3 else ""

            msg = (
                f"{highlight}📈 {symbol_display}\n\n"
                f"💰 Giá hiện tại: {entry_price}\n"
                f"📊 Điểm tín hiệu: {sig['score']}\n"
                f"📌 Lý do:\n- " + "\n- ".join(sig["reasons"]) + "\n\n"
                f"🕒 Thời gian: {get_vietnam_time().strftime('%H:%M %d/%m/%Y')}"
            )
            await bot.send_message(chat_id=S.TELEGRAM_ALLOWED_USER_ID, text=msg)

    except Exception as e:
        print(f"[ERROR] job_trade_signals: {e}")
        print(traceback.format_exc())

# =============================
# Đăng ký job sáng & tối
# =============================
def register_daily_jobs(job_queue):
    tz = pytz.timezone("Asia/Ho_Chi_Minh")
    job_queue.run_daily(job_morning_message, time=time(hour=6, minute=0, tzinfo=tz), name="morning_report")
    job_queue.run_daily(job_evening_summary, time=time(hour=22, minute=0, tzinfo=tz), name="evening_report")
