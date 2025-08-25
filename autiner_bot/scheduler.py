from telegram import Bot
from autiner_bot.settings import S
from autiner_bot.utils.state import get_state
from autiner_bot.utils.time_utils import get_vietnam_time
from autiner_bot.data_sources.mexc import (
    get_usdt_vnd_rate,
    get_top_futures,
    analyze_coin_trend,
)
import traceback
import pytz
from datetime import time

bot = Bot(token=S.TELEGRAM_BOT_TOKEN)


# =============================
# Format giá (gọn, không dư)
# =============================
def format_price(value: float, currency: str = "USD", vnd_rate: float | None = None) -> str:
    if currency == "VND":
        if not vnd_rate or vnd_rate <= 0:
            return "N/A"
        value = value * vnd_rate
        return f"{round(value):,}".replace(",", ".")
    else:
        return f"{value:.6f}".rstrip("0").rstrip(".")


# =============================
# Tạo tín hiệu
# =============================
def create_trade_signal(symbol, side, entry_raw, mode="Scalping",
                        currency_mode="USD", vnd_rate=None,
                        strength=0, reason="No data"):
    entry_price = format_price(entry_raw, currency_mode, vnd_rate)

    if side == "LONG":
        tp_val = entry_raw * (1.01 if mode == "Scalping" else 1.02)
        sl_val = entry_raw * (0.99 if mode == "Scalping" else 0.98)
    else:
        tp_val = entry_raw * (0.99 if mode == "Scalping" else 0.98)
        sl_val = entry_raw * (1.01 if mode == "Scalping" else 1.02)

    tp = format_price(tp_val, currency_mode, vnd_rate)
    sl = format_price(sl_val, currency_mode, vnd_rate)

    label = "Mạnh" if strength >= 70 else ("Tiêu chuẩn" if strength >= 50 else "Tham khảo")

    msg = (
        f"📈 {symbol.replace('_USDT','/'+currency_mode)} — {'🟢 LONG' if side=='LONG' else '🟥 SHORT'}\n\n"
        f"🟢 Loại lệnh: {mode}\n"
        f"🔹 Kiểu vào lệnh: Market\n"
        f"💰 Entry: {entry_price} {currency_mode}\n"
        f"🎯 TP: {tp} {currency_mode}\n"
        f"🛡️ SL: {sl} {currency_mode}\n"
        f"📊 Độ mạnh: {strength:.0f}% ({label})\n"
        f"📌 Lý do: {reason}\n"
        f"🕒 Thời gian: {get_vietnam_time().strftime('%H:%M %d/%m/%Y')}"
    )
    return msg


# =============================
# Gửi tín hiệu 30 phút/lần
# =============================
async def job_trade_signals(_=None):
    try:
        state = get_state()
        if not state["is_on"]:
            return

        currency_mode = state.get("currency_mode", "USD")
        vnd_rate = await get_usdt_vnd_rate() if currency_mode == "VND" else None

        coins = await get_top_futures(limit=15)
        if not coins:
            await bot.send_message(chat_id=S.TELEGRAM_ALLOWED_USER_ID,
                                   text="⚠️ Không lấy được dữ liệu coin.")
            return

        coin_signals = []
        for coin in coins:
            trend = await analyze_coin_trend(coin["symbol"])
            if trend:
                coin_signals.append({
                    "symbol": coin["symbol"],
                    "side": trend["side"],
                    "reason": trend["reason"],
                    "strength": trend["strength"],
                    "lastPrice": coin["lastPrice"]
                })

        if not coin_signals:
            await bot.send_message(chat_id=S.TELEGRAM_ALLOWED_USER_ID,
                                   text="⚠️ Không có tín hiệu.")
            return

        coin_signals.sort(key=lambda x: x["strength"], reverse=True)
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
                strength=coin["strength"],
                reason=coin["reason"]
            )
            if idx == 0:
                msg = msg.replace("📈", "📈⭐", 1)
            await bot.send_message(chat_id=S.TELEGRAM_ALLOWED_USER_ID, text=msg)

    except Exception as e:
        print(f"[ERROR] job_trade_signals: {e}")
        print(traceback.format_exc())


# =============================
# Setup job
# =============================
def setup_jobs(application):
    tz = pytz.timezone("Asia/Ho_Chi_Minh")

    for h in range(6, 22):
        for m in [0, 30]:
            application.job_queue.run_daily(job_trade_signals, time=time(h, m, 0, tzinfo=tz))

    print("✅ Scheduler đã setup thành công!")
