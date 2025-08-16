from telegram import Bot
from autiner_bot.settings import S
from autiner_bot.utils.state import get_state
from autiner_bot.utils.time_utils import get_vietnam_time
from autiner_bot.data_sources.mexc import get_top_moving_coins
from autiner_bot.data_sources.exchange import get_usdt_vnd_rate, get_market_sentiment
from autiner_bot.jobs.daily_reports import job_morning_message, job_evening_summary
import asyncio
import traceback
import pytz
from datetime import time

bot = Bot(token=S.TELEGRAM_BOT_TOKEN)

# =============================
# Format giá
# =============================
def format_price(value: float, currency: str = "USD", vnd_rate: float | None = None) -> str:
    try:
        if currency == "VND" and vnd_rate:
            value = value * vnd_rate
            return f"{value:,.0f} VND"
        return f"{value:.4f} {currency}"
    except:
        return str(value)

# =============================
# Tạo tín hiệu
# =============================
def create_trade_signal(coin):
    direction = "LONG" if coin["change_pct"] > 0 else "SHORT"
    order_type = "MARKET"
    tp_price = coin["lastPrice"] * (1 + (0.5/100 if direction == "LONG" else -0.5/100))
    sl_price = coin["lastPrice"] * (1 - (0.3/100 if direction == "LONG" else -0.3/100))

    strength = min(int(coin["score"] * 10), 100)
    return {
        "symbol": coin["symbol"],
        "side": direction,
        "orderType": order_type,
        "entry": coin["lastPrice"],
        "tp": tp_price,
        "sl": sl_price,
        "strength": strength,
        "reason": "; ".join(coin["signals"]) or f"Biến động {coin['change_pct']:.2f}%"
    }

# =============================
# Báo trước 1 phút
# =============================
async def job_trade_signals_notice():
    try:
        state = get_state()
        if not state["is_on"]:
            return
        await bot.send_message(chat_id=S.TELEGRAM_ALLOWED_USER_ID, text="⏳ 1 phút nữa sẽ có tín hiệu giao dịch!")
    except Exception as e:
        print(f"[ERROR] job_trade_signals_notice: {e}")
        print(traceback.format_exc())

# =============================
# Gửi tín hiệu
# =============================
async def job_trade_signals():
    try:
        state = get_state()
        if not state["is_on"]:
            return

        currency_mode = state.get("currency_mode", "USD")
        vnd_rate = None
        if currency_mode == "VND":
            vnd_rate = await get_usdt_vnd_rate()

        moving_coins = await get_top_moving_coins(limit=5)

        for coin in moving_coins:
            sig = create_trade_signal(coin)
            entry = format_price(sig["entry"], currency_mode, vnd_rate)
            tp = format_price(sig["tp"], currency_mode, vnd_rate)
            sl = format_price(sig["sl"], currency_mode, vnd_rate)

            highlight = "⭐ " if sig["strength"] >= 70 else ""
            side_icon = "🟩 LONG" if sig["side"] == "LONG" else "🟥 SHORT"

            msg = (
                f"{highlight}📈 {sig['symbol'].replace('_USDT', f'/{currency_mode}')}\n"
                f"{side_icon} | {sig['orderType']}\n"
                f"💰 Entry: {entry}\n🎯 TP: {tp}\n🛡️ SL: {sl}\n"
                f"📊 Độ mạnh: {sig['strength']}%\n"
                f"📌 Lý do: {sig['reason']}\n"
                f"🕒 {get_vietnam_time().strftime('%H:%M %d/%m/%Y')}"
            )
            await bot.send_message(chat_id=S.TELEGRAM_ALLOWED_USER_ID, text=msg)

    except Exception as e:
        print(f"[ERROR] job_trade_signals: {e}")
        print(traceback.format_exc())

# =============================
# Đăng ký job sáng/tối
# =============================
def register_daily_jobs(job_queue):
    tz = pytz.timezone("Asia/Ho_Chi_Minh")
    job_queue.run_daily(job_morning_message, time=time(hour=6, minute=0, tzinfo=tz))
    job_queue.run_daily(job_evening_summary, time=time(hour=22, minute=0, tzinfo=tz))
