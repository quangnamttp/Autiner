from telegram import Bot
from autiner_bot.settings import S
from autiner_bot.utils.state import get_state
from autiner_bot.utils.time_utils import get_vietnam_time
from autiner_bot.data_sources.mexc import (
    get_usdt_vnd_rate,
    analyze_market_trend,   # ✅ dùng chung
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
# Bản tin buổi sáng
# =============================
async def job_morning_message(_=None):
    try:
        state = get_state()
        if not state["is_on"]:
            return

        vnd_rate = await get_usdt_vnd_rate()
        market = await analyze_market_trend(limit=20)   # ✅ lấy top 20 coin

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

        # 🔧 sửa lại key: market["top"]
        for c in market["top"][:5]:
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
        market = await analyze_market_trend(limit=20)

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

        # 🔧 sửa lại key: market["top"]
        for c in market["top"][:5]:
            msg += f" • {c['symbol'].replace('_USDT','/USDT')} | {c['change_pct']:+.2f}%\n"

        msg += "\n📊 Đến giờ nghĩ ngơi bạn hãy kiểm tra lại và chốt lệnh quản lí vốn thật tốt để mai bắt đầu công việc. Chúc bạn ngủ ngon. 🚀"

        await bot.send_message(chat_id=S.TELEGRAM_ALLOWED_USER_ID, text=msg)
    except Exception as e:
        print(f"[ERROR] job_evening_summary: {e}")
        print(traceback.format_exc())
