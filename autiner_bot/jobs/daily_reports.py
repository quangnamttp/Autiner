# autiner_bot/jobs/daily_reports.py
from telegram import Bot
from autiner_bot.settings import S
from autiner_bot.utils.state import get_state
from autiner_bot.utils.time_utils import get_vietnam_time
from autiner_bot.data_sources.mexc import (
    get_market_sentiment,
    get_market_funding_volume,
    get_usdt_vnd_rate,
    get_top20_futures,
)

bot = Bot(token=S.TELEGRAM_BOT_TOKEN)

# ===== BUỔI SÁNG =====
async def job_morning_message():
    """Gửi thông báo buổi sáng lúc 6h."""
    try:
        state = get_state()
        if not state["is_on"]:
            return

        now = get_vietnam_time()
        weekday = now.strftime("%A")
        date_str = now.strftime("%d/%m/%Y")

        # Chuyển sang tiếng Việt
        weekday_vi = {
            "Monday": "Thứ Hai",
            "Tuesday": "Thứ Ba",
            "Wednesday": "Thứ Tư",
            "Thursday": "Thứ Năm",
            "Friday": "Thứ Sáu",
            "Saturday": "Thứ Bảy",
            "Sunday": "Chủ Nhật"
        }.get(weekday, weekday)

        # Giá USD -> VND
        vnd_rate = await get_usdt_vnd_rate()
        usd_to_vnd = f"{vnd_rate:,.0f}".replace(",", ".") if vnd_rate else "N/A"

        # Xu hướng thị trường
        sentiment = await get_market_sentiment()

        # Funding & Volume
        funding_info = await get_market_funding_volume()

        # Top 5 coin nổi bật
        top_coins = await get_top20_futures(limit=5)

        # Tính xu hướng chung
        trend = "📈 Tăng" if sentiment["long"] >= sentiment["short"] else "📉 Giảm"

        # Danh sách coin
        coin_lines = []
        for c in top_coins:
            symbol = c['symbol'].replace('_USDT', '/USDT')
            change_pct = f"{c['change_pct']:+.2f}%"
            coin_lines.append(f" • {symbol:<8} | {change_pct:>7}")
        coins_table = "\n".join(coin_lines)

        # Tin nhắn cuối
        msg = (
            f"📅 Hôm nay {weekday_vi}, {date_str}\n"
            f"🌞 06:00 — Chào buổi sáng anh Trương ☀️\n\n"
            f"💵 1 USD = {usd_to_vnd} VND\n"
            f"📊 Thị trường: 🟢 LONG {sentiment['long']:.1f}% | 🔴 SHORT {sentiment['short']:.1f}%\n"
            f"📌 Xu hướng chung: {trend}\n"
            f"💹 Funding: {funding_info['funding']}\n"
            f"📈 Volume: {funding_info['volume']}\n\n"
            f"🔥 Top 5 đồng coin nổi bật:\n{coins_table}\n\n"
            f"⏳ Trong 15 phút nữa sẽ có tín hiệu. Chuẩn bị sẵn sàng để vào lệnh nhé! 🚀"
        )

        await bot.send_message(chat_id=S.TELEGRAM_ALLOWED_USER_ID, text=msg)

    except Exception as e:
        print(f"[ERROR] job_morning_message: {e}")


# ===== BUỔI TỐI =====
async def job_evening_summary():
    """Gửi thông báo kết thúc ngày lúc 22h."""
    try:
        state = get_state()
        if not state["is_on"]:
            return

        now = get_vietnam_time()
        weekday = now.strftime("%A")
        date_str = now.strftime("%d/%m/%Y")

        # Chuyển sang tiếng Việt
        weekday_vi = {
            "Monday": "Thứ Hai",
            "Tuesday": "Thứ Ba",
            "Wednesday": "Thứ Tư",
            "Thursday": "Thứ Năm",
            "Friday": "Thứ Sáu",
            "Saturday": "Thứ Bảy",
            "Sunday": "Chủ Nhật"
        }.get(weekday, weekday)

        # Xu hướng thị trường để tổng kết
        sentiment = await get_market_sentiment()
        funding_info = await get_market_funding_volume()
        trend = "📈 Tăng" if sentiment["long"] >= sentiment["short"] else "📉 Giảm"

        msg = (
            f"🌒 22:00 — {weekday_vi}, {date_str}\n\n"
            f"📌 Kết thúc ngày giao dịch hôm nay.\n"
            f"📊 Hiệu suất: 🟢 LONG {sentiment['long']:.1f}% | 🔴 SHORT {sentiment['short']:.1f}%\n"
            f"📌 Xu hướng chung: {trend}\n"
            f"💹 Funding: {funding_info['funding']}\n"
            f"📈 Volume: {funding_info['volume']}\n\n"
            f"🔒 Hãy nhớ quản lý vốn và chốt lệnh để tránh biến động ban đêm.\n\n"
            f"🌙 Chúc anh Trương ngủ ngon 🤗"
        )

        await bot.send_message(chat_id=S.TELEGRAM_ALLOWED_USER_ID, text=msg)

    except Exception as e:
        print(f"[ERROR] job_evening_summary: {e}")
