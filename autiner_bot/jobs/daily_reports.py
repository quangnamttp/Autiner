# autiner_bot/jobs/daily_reports.py

from telegram import Bot
from autiner_bot.settings import S
from autiner_bot.utils.state import get_state
from autiner_bot.utils.time_utils import get_vietnam_time
from autiner_bot.data_sources.mexc import (
    get_top_moving_coins,
    get_market_sentiment,
    get_market_funding_volume
)
from autiner_bot.data_sources.exchange import get_usdt_vnd_rate

bot = Bot(token=S.TELEGRAM_BOT_TOKEN)


# ==== Buổi sáng ====
async def job_morning_message():
    """Gửi thông báo buổi sáng lúc 6h."""
    try:
        state = get_state()
        if not state["is_on"]:
            return

        now = get_vietnam_time()
        weekday_vi = now.strftime("%A")  # Thứ tiếng Anh
        weekdays_map = {
            "Monday": "Thứ Hai", "Tuesday": "Thứ Ba", "Wednesday": "Thứ Tư",
            "Thursday": "Thứ Năm", "Friday": "Thứ Sáu",
            "Saturday": "Thứ Bảy", "Sunday": "Chủ Nhật"
        }
        weekday = weekdays_map.get(weekday_vi, weekday_vi)
        date_str = now.strftime("%d/%m/%Y")

        # Giá USD -> VND
        vnd_rate = await get_usdt_vnd_rate()
        usd_to_vnd = f"{vnd_rate:,.0f}".replace(",", ".") if vnd_rate else "N/A"

        # Xu hướng thị trường
        sentiment = await get_market_sentiment()

        # Top 5 coin tăng trưởng mạnh nhất
        top_coins = await get_top_moving_coins(limit=5)

        # Funding & Volume
        funding_info = await get_market_funding_volume()

        msg = (
            f"📅 Hôm nay {weekday} — {date_str}\n"
            f"🌞 06:00 — Chào buổi sáng anh Trương ☀️, thị trường hôm nay có nhiều biến động, mình cùng theo dõi nhé!\n\n"
            f"💵 1 USD = {usd_to_vnd} VND\n"
            f"📊 Thị trường nghiêng về: LONG {sentiment['long']:.1f}% | SHORT {sentiment['short']:.1f}%\n\n"
            f"🔥 5 đồng coin nổi bật:\n" +
            "\n".join([f"• {c['symbol'].replace('_USDT','/USDT')} {c['change_pct']:.2f}%" for c in top_coins]) + "\n\n"
            f"💹 Funding: {funding_info['funding']}\n"
            f"📈 Volume: {funding_info['volume']}\n"
            f"📌 Xu hướng: {funding_info['trend']}\n\n"
            f"⏳ Trong 15 phút nữa sẽ có tín hiệu. Chuẩn bị sẵn sàng để vào lệnh nhé!"
        )

        await bot.send_message(chat_id=S.TELEGRAM_ALLOWED_USER_ID, text=msg)

    except Exception as e:
        print(f"[ERROR] job_morning_message: {e}")


# ==== Buổi tối ====
async def job_evening_summary():
    """Gửi thông báo kết thúc ngày lúc 22h."""
    try:
        state = get_state()
        if not state["is_on"]:
            return

        now = get_vietnam_time()
        weekday_vi = now.strftime("%A")
        weekdays_map = {
            "Monday": "Thứ Hai", "Tuesday": "Thứ Ba", "Wednesday": "Thứ Tư",
            "Thursday": "Thứ Năm", "Friday": "Thứ Sáu",
            "Saturday": "Thứ Bảy", "Sunday": "Chủ Nhật"
        }
        weekday = weekdays_map.get(weekday_vi, weekday_vi)
        date_str = now.strftime("%d/%m/%Y")

        msg = (
            f"🌒 22:00 — {weekday}, {date_str}\n\n"
            f"Kết thúc ngày giao dịch, bạn hãy quản lý tín hiệu tốt nhé.\n"
            f"Chốt lệnh trước khi ngủ để tránh biến động về đêm…\n\n"
            f"Ngày mai chúng ta sẽ bắt đầu công việc mới! 🌱\n\n"
            f"🌙 Chúc anh Trương ngủ ngon 🤗"
        )

        await bot.send_message(chat_id=S.TELEGRAM_ALLOWED_USER_ID, text=msg)

    except Exception as e:
        print(f"[ERROR] job_evening_summary: {e}")
