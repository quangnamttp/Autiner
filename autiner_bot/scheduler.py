from telegram import Bot
from autiner_bot.settings import S
from autiner_bot.utils.state import get_state
from autiner_bot.utils.time_utils import get_vietnam_time
from autiner_bot.data_sources.mexc import get_top_moving_coins
from autiner_bot.data_sources.exchange import get_usdt_vnd_rate
import asyncio
import pytz
from datetime import time
import traceback

bot = Bot(token=S.TELEGRAM_BOT_TOKEN)

def format_price_usd_vnd(value_usd, vnd_rate):
    usd_str = f"{value_usd:,.6f}".rstrip("0").rstrip(".").replace(",", ".")
    vnd_val = value_usd * vnd_rate
    vnd_str = f"{vnd_val:,.0f}".replace(",", ".")
    return f"{usd_str} USD | {vnd_str} VND"

def create_trade_signal(symbol, last_price, change_pct):
    direction = "LONG" if change_pct > 0 else "SHORT"
    order_type = "MARKET"
    tp_pct = 0.5 if direction == "LONG" else -0.5
    sl_pct = -0.3 if direction == "LONG" else 0.3

    return {
        "symbol": symbol,
        "side": direction,
        "orderType": order_type,
        "entry": last_price,
        "tp": last_price * (1 + tp_pct / 100),
        "sl": last_price * (1 + sl_pct / 100),
        "strength": min(int(abs(change_pct) * 10), 100),
        "reason": f"Biến động {change_pct:.2f}% trong 15 phút"
    }

async def job_trade_signals():
    try:
        state = get_state()
        if not state["is_on"]:
            return

        moving_task = asyncio.create_task(get_top_moving_coins(limit=5))
        rate_task = asyncio.create_task(get_usdt_vnd_rate())
        moving_coins, vnd_rate = await asyncio.gather(moving_task, rate_task)

        for c in moving_coins:
            sig = create_trade_signal(c["symbol"], c["lastPrice"], c["change_pct"])
            entry_price = format_price_usd_vnd(sig["entry"], vnd_rate)
            tp_price = format_price_usd_vnd(sig["tp"], vnd_rate)
            sl_price = format_price_usd_vnd(sig["sl"], vnd_rate)

            symbol_display = sig["symbol"].replace("_USDT", "/USD")
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
