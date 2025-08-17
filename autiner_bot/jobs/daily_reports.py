from telegram import Bot
from autiner_bot.settings import S
from autiner_bot.utils.state import get_state
from autiner_bot.utils.time_utils import get_vietnam_time
from autiner_bot.data_sources.mexc import (
    get_usdt_vnd_rate,
    get_top20_futures,
    get_funding_rate,
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

        # Tính volume
        total_volume = sum([c.get("volume", 0) for c in coins])
        total_volume_bil = total_volume / 1e9  # đổi sang tỷ USD

        # Tính long/short giả lập (dựa trên thay đổi %)
        ups = [c for c in coins if c.get("change_pct", 0) > 0]
        downs = [c for c in coins if c.get("change_pct", 0) < 0]

        total = len(ups) + len(downs)
        if total == 0:
            long_pct, short_pct = 50.0, 50.0
        else:
            long_pct = round(len(ups) / total * 100, 1)
            short_pct = round(len(downs) / total * 100, 1)

        # Xu hướng chung = tổng % thay đổi giá
        avg_change = sum([c.get("change_pct", 0) for c in coins]) / len(coins)
        trend = "📈 Tăng" if avg_change > 0 else "📉 Giảm"

        # Funding (lấy BTC làm đại diện)
        funding = await get_funding_rate("BTC_USDT")

        # Top 5 coin nổi bật theo % biến động
        top5 = sorted(coins, key=lambda x: abs(x.get("change_pct", 0)), reverse=True)[:5]

        return {
            "long": long_pct,
            "short": short_pct,
            "trend": trend,
            "funding": f"{funding:.4f}%" if funding else "N/A",
            "volume": f"{total_volume_bil:.1f}B",
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
            msg += f" • {c['symbol'].replace('_USDT','/USDT')} |  {c['change_pct']:+.2f}%\n"

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
            msg += f" • {c['symbol'].replace('_USDT','/USDT')} |  {c['change_pct']:+.2f}%\n"

        msg += "\n📊 Hiệu suất lệnh sẽ được tổng hợp trong bản nâng cấp sau. 🚀"

        await bot.send_message(chat_id=S.TELEGRAM_ALLOWED_USER_ID, text=msg)
    except Exception as e:
        print(f"[ERROR] job_evening_summary: {e}")
        print(traceback.format_exc())
