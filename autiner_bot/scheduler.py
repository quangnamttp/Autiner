# autiner_bot/scheduler.py
from telegram import Bot
from autiner_bot.settings import S
from autiner_bot.utils.state import get_state
from autiner_bot.utils.time_utils import get_vietnam_time
from autiner_bot.data_sources.mexc import (
    get_usdt_vnd_rate,
    analyze_coin_signal_v2,
    get_top20_futures,
)
from autiner_bot.jobs.daily_reports import job_morning_message, job_evening_summary

import traceback
import pytz
import random
from datetime import time

bot = Bot(token=S.TELEGRAM_BOT_TOKEN)

_last_selected = []


def format_price(value: float, currency: str = "USD", vnd_rate: float | None = None) -> str:
    try:
        if currency == "VND":
            if not vnd_rate or vnd_rate <= 0:
                return "N/A VND"
            value = value * vnd_rate
            s = f"{value:.10f}".rstrip("0").rstrip(".")
            if "." in s:
                int_part, dec_part = s.split(".")
                int_part = f"{int(int_part):,}".replace(",", ".")
                s = f"{int_part}.{dec_part}"
            else:
                s = f"{int(s):,}".replace(",", ".")
            return s
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


async def create_trade_signal(coin: dict, mode: str = "SCALPING", currency_mode="USD", vnd_rate=None):
    try:
        signal = await analyze_coin_signal_v2(coin)
        entry_price = format_price(signal["entry"], currency_mode, vnd_rate)
        tp_price = format_price(signal["tp"], currency_mode, vnd_rate)
        sl_price = format_price(signal["sl"], currency_mode, vnd_rate)
        symbol_display = coin["symbol"].replace("_USDT", f"/{currency_mode.upper()}")
        side_icon = "🟩 LONG" if signal["direction"] == "LONG" else "🟥 SHORT"

        if signal["strength"] >= 70:
            label = "⭐ TÍN HIỆU MẠNH ⭐"
        elif signal["strength"] <= 60:
            label = "⚠️ THAM KHẢO ⚠️"
        else:
            label = ""

        msg = (
            f"{label}\n"
            f"📈 {symbol_display}\n"
            f"{side_icon}\n"
            f"📌 Chế độ: {mode.upper()}\n"
            f"📑 Loại lệnh: {signal['orderType']}\n"
            f"💰 Entry: {entry_price} {currency_mode}\n"
            f"🎯 TP: {tp_price} {currency_mode}\n"
            f"🛡️ SL: {sl_price} {currency_mode}\n"
            f"📊 Độ mạnh: {signal['strength']}%\n"
            f"📌 Lý do:\n{signal['reason']}\n"
            f"🕒 {get_vietnam_time().strftime('%H:%M %d/%m/%Y')}"
        )
        return msg
    except Exception as e:
        print(f"[ERROR] create_trade_signal: {e}")
        print(traceback.format_exc())
        return "⚠️ Không tạo được tín hiệu cho coin này."


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

        all_coins = await get_top20_futures(limit=20)
        if not all_coins:
            await bot.send_message(
                chat_id=S.TELEGRAM_ALLOWED_USER_ID,
                text="⚠️ Không lấy được dữ liệu coin từ sàn."
            )
            return

        selected = [c for c in all_coins if c["symbol"] in ["BTC_USDT", "ETH_USDT"]]
        volatile = [c for c in all_coins if abs(c["change_pct"]) >= 5 and c["symbol"] not in ["BTC_USDT", "ETH_USDT"]]
        volatile = [c for c in volatile if c["symbol"] not in _last_selected]
        remaining = [c for c in all_coins if c["symbol"] not in _last_selected and c["symbol"] not in ["BTC_USDT", "ETH_USDT"]]

        while len(selected) < 5:
            if volatile:
                selected.append(volatile.pop(0))
            elif remaining:
                choice = random.choice(remaining)
                selected.append(choice)
                remaining.remove(choice)
            else:
                break

        _last_selected = ([c["symbol"] for c in selected] + _last_selected)[:10]

        print(f"[DEBUG] Selected {len(selected)} coins:")
        for c in selected:
            print(f" -> {c['symbol']} | vol={c['volume']} | change={c['change_pct']}")

        for i, coin in enumerate(selected):
            try:
                mode = "SCALPING" if i < 3 else "SWING"
                msg = await create_trade_signal(coin, mode, currency_mode, vnd_rate)
                await bot.send_message(chat_id=S.TELEGRAM_ALLOWED_USER_ID, text=msg)
            except Exception as e:
                print(f"[ERROR] gửi tín hiệu coin {coin.get('symbol')}: {e}")
                continue

    except Exception as e:
        print(f"[ERROR] job_trade_signals: {e}")
        print(traceback.format_exc())


def register_daily_jobs(job_queue):
    tz = pytz.timezone("Asia/Ho_Chi_Minh")
    job_queue.run_daily(job_morning_message, time=time(hour=6, minute=0, tzinfo=tz), name="morning_report")
    job_queue.run_daily(job_evening_summary, time=time(hour=22, minute=0, tzinfo=tz), name="evening_report")
    job_queue.run_repeating(job_trade_signals_notice, interval=1800, first=time(hour=6, minute=14, tzinfo=tz), name="trade_signals_notice")
    job_queue.run_repeating(job_trade_signals, interval=1800, first=time(hour=6, minute=15, tzinfo=tz), name="trade_signals")
