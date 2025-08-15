# autiner_bot/scheduler.py
from telegram import Bot
from autiner_bot.settings import S
from autiner_bot.utils.state import get_state
from autiner_bot.utils.time_utils import get_vietnam_time
from autiner_bot.data_sources.mexc import get_top_moving_coins
from autiner_bot.data_sources.exchange import get_usdt_vnd_rate
from autiner_bot.jobs.daily_reports import job_morning_message, job_evening_summary
import traceback
import pytz
from datetime import time

bot = Bot(token=S.TELEGRAM_BOT_TOKEN)

# =============================
# Hàm format_price mới
# =============================
def format_price(value: float, currency: str = "VND", vnd_rate: float = None) -> str:
    """
    Định dạng giá hiển thị:
    - USD: giữ nguyên giá từ MEXC, thêm dấu . tách nghìn, giữ nguyên số thập phân.
    - VND: luôn quy đổi, không làm tròn vô nghĩa, bỏ số 0 & dấu thập phân vô nghĩa phía trước.
    """
    try:
        if currency == "VND":
            if not vnd_rate or vnd_rate <= 0:
                vnd_rate = 25_000
            value = value * vnd_rate

            if value >= 1000:
                # Lớn hơn hoặc bằng 1000 => tách nghìn, giữ 2 số thập phân
                return f"{value:,.2f}".replace(",", ".").rstrip('0').rstrip('.') + " VND"
            else:
                # Nhỏ hơn 1000 => hiển thị tối đa 4 số thập phân
                return f"{value:.4f}".rstrip('0').rstrip('.') + " VND"

        else:  # USD
            if value >= 1:
                return f"{value:,.8f}".replace(",", ".").rstrip('0').rstrip('.')
            else:
                return f"{value:.8f}".rstrip('0').rstrip('.')
    except Exception:
        return f"{value} {currency}"


# =============================
# Hàm tạo tín hiệu
# =============================
def create_trade_signal(symbol, last_price, change_pct):
    direction = "LONG" if change_pct > 0 else "SHORT"
    order_type = "MARKET" if abs(change_pct) > 2 else "LIMIT"

    tp_pct = 0.5 if direction == "LONG" else -0.5
    sl_pct = -0.3 if direction == "LONG" else 0.3

    tp_price = last_price * (1 + tp_pct / 100)
    sl_price = last_price * (1 + sl_pct / 100)

    return {
        "symbol": symbol,
        "side": direction,
        "orderType": order_type,
        "entry": last_price,
        "tp": tp_price,
        "sl": sl_price,
        "strength": min(int(abs(change_pct) * 10), 100),
        "reason": f"Biến động {change_pct:.2f}% trong 15 phút"
    }


# =============================
# Gửi thông báo 1 phút trước tín hiệu
# =============================
async def job_trade_signals_notice():
    try:
        state = get_state()
        if not state["is_on"]:
            return
        await bot.send_message(
            chat_id=S.TELEGRAM_ALLOWED_USER_ID,
            text="⏳ 1 phút nữa sẽ có tín hiệu giao dịch!"
        )
    except Exception as e:
        print(f"[ERROR] job_trade_signals_notice: {e}")
        print(traceback.format_exc())


# =============================
# Gửi tín hiệu giao dịch
# =============================
async def job_trade_signals():
    try:
        state = get_state()
        if not state["is_on"]:
            return

        vnd_rate = None
        if state["currency_mode"] == "VND":
            vnd_rate = await get_usdt_vnd_rate()

        moving_coins = await get_top_moving_coins(limit=5)
        signals = [create_trade_signal(c["symbol"], c["lastPrice"], c["change_pct"]) for c in moving_coins]

        for sig in signals:
            entry_price = format_price(sig['entry'], state['currency_mode'], vnd_rate)
            tp_price = format_price(sig['tp'], state['currency_mode'], vnd_rate)
            sl_price = format_price(sig['sl'], state['currency_mode'], vnd_rate)

            if state['currency_mode'] == "VND":
                symbol_display = sig['symbol'].replace("_USDT", "/VND")
            else:
                symbol_display = sig['symbol'].replace("_USDT", "/USD")

            side_icon = "🟩 LONG" if sig["side"] == "LONG" else "🟥 SHORT"
            highlight = "⭐ " if sig["strength"] >= 70 else ""

            msg = (
                f"{highlight}📈 {symbol_display} — {side_icon}\n\n"
                f"🔹 Kiểu vào lệnh: {sig['orderType']}\n"
                f"💰 Entry: {entry_price}\n"
                f"🎯 TP: {tp_price}\n"
                f"🛡️ SL: {sl_price}\n"
                f"📊 Độ mạnh: {sig['strength']}%\n"
                f"📌 Lý do: {sig['reason']}\n"
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
