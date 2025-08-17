# autiner_bot/jobs/daily_reports.py
from telegram import Bot
from autiner_bot.settings import S
from autiner_bot.utils.state import get_state
from autiner_bot.utils.time_utils import get_vietnam_time
from autiner_bot.data_sources.mexc import (
    get_usdt_vnd_rate,
    get_top20_futures,
    get_market_funding_volume,
)

import pytz
import traceback
from datetime import datetime

bot = Bot(token=S.TELEGRAM_BOT_TOKEN)


# =============================
# Hàm lấy tổng quan thị trường
# =============================
async def get_market_overview():
    try:
        coins = await get_top20_futures(limit=20)
        if not coins:
            return {
                "long": 50.0,
                "short": 50.0,
                "trend": "Không xác định",
                "funding": "N/A",
                "volume": "N/A",
                "top5": []
            }

        ups = [c for c in coins if c.get("change_pct", 0) > 0]
        downs = [c for c in coins if c.get("change_pct", 0) < 0]

        total = len(ups) + len(downs)
        if total == 0:
            long_pct, short_pct = 50.0, 50.0
        else:
            long_pct = round(len(ups) / total * 100, 1)
            short_pct = round(len(downs) / total * 100, 1)

        avg_change = sum([c.get("change_pct", 0) for c in coins]) / len(coins)
        trend = "📈 Tăng" if avg_change > 0 else "📉 Giảm"

        market_data = await get_market_funding_volume()

        top5 = sorted(coins, key=lambda x: abs(x.get("change_pct", 0)), reverse=True)[:5]

        return {
            "long": long_pct,
            "short": short_pct,
            "trend": trend,
            "funding": market_data["funding"],
            "volume": market_data["volume"],
            "top5": top5
        }
    except Exception as e:
        print(f"[ERROR] get_market_overview: {e}")
        print(traceback.format_exc())
        return None


# =============================
# Bản tin buổi sáng
# =============================
async def job_morning_message(_=None):
    try:
        state = get_state()
        if not state["is_on"]:
            return

        vnd_rate = await get_usdt_vnd_rate()
        market = await get_market_overview()
        today = get_vietnam_time().strftime("%A, %d/%m/%Y")

        msg = (
            f"📅 Hôm nay {today}\n"
            f"🌞 06:00 — Chào buổi sáng anh Trương ☀️\n\n"
            f"💵 1 USD = {vnd_rate:,.0f} VND\n"
            f"📊 Thị trường: 🟢 LONG {market['long']}% | 🔴 SHORT {market['short']}%\n"
            f"📌 Xu hướng chung: {market['trend']}\n"
            f"💹 Funding: {market['funding']}\n"
            f"📈 Volume: {market['volume']}\n\n"
            f"🔥 Top 5 đồng coin nổi bật:\n"
        )

        for c in market["top5"]:
            msg += f" • {c['symbol'].replace('_USDT','/USDT')} | {c['change_pct']:+.2f}%\n"

        msg += "\n⏳ Trong 15 phút nữa sẽ có tín hiệu. Chuẩn bị sẵn sàng để vào lệnh nhé! 🚀"

        await bot.send_message(chat_id=S.TELEGRAM_ALLOWED_USER_ID, text=msg)
    except Exception as e:
        print(f"[ERROR] job_morning_message: {e}")
        print(traceback.format_exc())


# =============================
# Bản tin buổi tối
# =============================
async def job_evening_summary(_=None):
    try:
        state = get_state()
        if not state["is_on"]:
            return

        vnd_rate = await get_usdt_vnd_rate()
        market = await get_market_overview()
        today = get_vietnam_time().strftime("%A, %d/%m/%Y")

        msg = (
            f"📅 Hôm nay {today}\n"
            f"🌙 22:00 — Tổng kết phiên giao dịch 🌙\n\n"
            f"💵 1 USD = {vnd_rate:,.0f} VND\n"
            f"📊 Thị trường: 🟢 LONG {market['long']}% | 🔴 SHORT {market['short']}%\n"
            f"📌 Xu hướng chung: {market['trend']}\n"
            f"💹 Funding: {market['funding']}\n"
            f"📈 Volume: {market['volume']}\n\n"
            f"🔥 Top 5 đồng coin nổi bật:\n"
        )

        for c in market["top5"]:
            msg += f" • {c['symbol'].replace('_USDT','/USDT')} | {c['change_pct']:+.2f}%\n"

        msg += "\n📊 Hiệu suất lệnh sẽ được tổng hợp trong bản nâng cấp sau. 🚀"

        await bot.send_message(chat_id=S.TELEGRAM_ALLOWED_USER_ID, text=msg)
    except Exception as e:
        print(f"[ERROR] job_evening_summary: {e}")
        print(traceback.format_exc())
