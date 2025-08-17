# autiner_bot/jobs/daily_reports.py
from telegram import Bot
from autiner_bot.settings import S
from autiner_bot.utils.state import get_state
from autiner_bot.utils.time_utils import get_vietnam_time
from autiner_bot.data_sources.mexc import (
    get_market_sentiment,
    get_market_funding_volume,
    get_usdt_vnd_rate
)
from autiner_bot.strategies.trend_detector import get_top20_futures   # ✅ thay thế get_top_signals

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

        # Chuyển sang tiếng Việt cho thứ
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

        # Top 5 coin nổi bật (từ top 20 futures theo volume)
        top_coins = await get_top20_futures(limit=5)

        # Funding & Volume
        funding_info = await get_market_funding_volume()

        # Thông điệp theo tình hình
        if sentiment["short"] > 60 or sum(1 for c in top_coins if c["change_pct"] < 0) >= 3:
            greeting = (
                f"🌞 06:00 — Chào buổi sáng anh Trương ☀️\n"
                f"Thị trường hôm nay có dấu hiệu **giảm mạnh**, hãy cẩn trọng nhé!"
            )
        else:
            greeting = (
                f"🌞 06:00 — Chào buổi sáng anh Trương ☀️\n"
                f"Thị trường hôm nay có nhiều **biến động**, mình cùng theo dõi nhé!"
            )

        # Danh sách top coin format dạng bảng
        coin_lines = []
        for c in top_coins:
            symbol = c['symbol'].replace('_USDT', '/USDT')
            change_pct = f"{c['change_pct']:+.2f}%"
            coin_lines.append(f"{symbol:<10} | {change_pct:>7}")

        coins_table = "\n".join(coin_lines)

        # Ghép tin nhắn
        msg = (
            f"📅 Hôm nay {weekday_vi}, {date_str}\n"
            f"{greeting}\n\n"
            f"💵 1 USD = {usd_to_vnd} VND\n"
            f"📊 Thị trường: LONG {sentiment['long']:.1f}% | SHORT {sentiment['short']:.1f}%\n\n"
            f"🔥 Top 5 đồng coin nổi bật:\n"
            f"```\n{coins_table}\n```\n"
            f"💹 Funding: {funding_info['funding']}\n"
            f"📈 Volume: {funding_info['volume']}\n"
            f"📌 Xu hướng: {funding_info['trend']}\n\n"
            f"⏳ Trong 15 phút nữa sẽ có tín hiệu. Chuẩn bị sẵn sàng để vào lệnh nhé!"
        )

        await bot.send_message(chat_id=S.TELEGRAM_ALLOWED_USER_ID, text=msg, parse_mode="Markdown")

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
        date_str = now.strftime("%d/%m/%Y")

        msg = (
            f"🌒 22:00 — {date_str}\n\n"
            f"📌 Kết thúc ngày giao dịch, hãy quản lý tín hiệu thật tốt.\n"
            f"🔒 Chốt lệnh trước khi ngủ để tránh biến động về đêm.\n\n"
            f"🌙 Chúc anh Trương ngủ ngon 🤗"
        )

        await bot.send_message(chat_id=S.TELEGRAM_ALLOWED_USER_ID, text=msg)

    except Exception as e:
        print(f"[ERROR] job_evening_summary: {e}")
