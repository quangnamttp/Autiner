from telegram import Bot
from autiner_bot.settings import S
from autiner_bot.utils.state import get_state
from autiner_bot.utils.time_utils import get_vietnam_time
from autiner_bot.data_sources.mexc import (
    get_usdt_vnd_rate,
    get_top30_futures,   # ✅ đổi từ get_top20_futures
)

import traceback

bot = Bot(token=S.TELEGRAM_BOT_TOKEN)

# Bảng dịch ngày sang tiếng Việt
VIETNAMESE_DAYS = {
    "Monday": "Thứ Hai",
    "Tuesday": "Thứ Ba",
    "Wednesday": "Thứ Tư",
    "Thursday": "Thứ Năm",
    "Friday": "Thứ Sáu",
    "Saturday": "Thứ Bảy",
    "Sunday": "Chủ Nhật",
}


# =============================
# Hàm lấy tổng quan thị trường
# =============================
async def get_market_overview():
    try:
        coins = await get_top30_futures(limit=20)   # ✅ vẫn giữ limit=20 cho bản tin
        if not coins:
            return {
                "long": 50.0,
                "short": 50.0,
                "trend": "❓ Không xác định",
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

        # Đồng bộ xu hướng theo Long/Short
        if long_pct > short_pct:
            trend = "📈 Xu hướng TĂNG (phe LONG chiếm ưu thế)"
        elif short_pct > long_pct:
            trend = "📉 Xu hướng GIẢM (phe SHORT chiếm ưu thế)"
        else:
            trend = "⚖️ Thị trường cân bằng"

        # Top 5 coin biến động mạnh nhất
        top5 = sorted(coins, key=lambda x: abs(x.get("change_pct", 0)), reverse=True)[:5]

        return {
            "long": long_pct,
            "short": short_pct,
            "trend": trend,
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

        dt = get_vietnam_time()
        weekday_en = dt.strftime("%A")
        weekday_vi = VIETNAMESE_DAYS.get(weekday_en, weekday_en)
        today = f"{weekday_vi}, {dt.strftime('%d/%m/%Y')}"

        msg = (
            f"📅 Hôm nay {today}\n"
            f"🌞 06:00 — Chào buổi sáng anh Trương ☀️\n\n"
            f"💵 1 USD = {vnd_rate:,.0f} VND\n"
            f"📊 Thị trường: 🟢 LONG {market['long']}% | 🔴 SHORT {market['short']}%\n"
            f"{market['trend']}\n\n"
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

        dt = get_vietnam_time()
        weekday_en = dt.strftime("%A")
        weekday_vi = VIETNAMESE_DAYS.get(weekday_en, weekday_en)
        today = f"{weekday_vi}, {dt.strftime('%d/%m/%Y')}"

        msg = (
            f"📅 Hôm nay {today}\n"
            f"🌙 22:00 — Tổng kết phiên giao dịch 🌙\n\n"
            f"💵 1 USD = {vnd_rate:,.0f} VND\n"
            f"📊 Thị trường: 🟢 LONG {market['long']}% | 🔴 SHORT {market['short']}%\n"
            f"{market['trend']}\n\n"
            f"🔥 Top 5 đồng coin nổi bật:\n"
        )

        for c in market["top5"]:
            msg += f" • {c['symbol'].replace('_USDT','/USDT')} | {c['change_pct']:+.2f}%\n"

        msg += "\n📊 Hiệu suất lệnh sẽ được tổng hợp trong bản nâng cấp sau. 🚀"

        await bot.send_message(chat_id=S.TELEGRAM_ALLOWED_USER_ID, text=msg)
    except Exception as e:
        print(f"[ERROR] job_evening_summary: {e}")
        print(traceback.format_exc())
