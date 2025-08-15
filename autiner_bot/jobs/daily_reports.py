from telegram import Bot
from autiner_bot.settings import S
from autiner_bot.utils.state import get_state
from autiner_bot.utils.time_utils import get_vietnam_time
from autiner_bot.data_sources.mexc import get_top_moving_coins
from autiner_bot.data_sources.exchange import get_usdt_vnd_rate, get_market_sentiment, get_market_funding_volume

bot = Bot(token=S.TELEGRAM_BOT_TOKEN)

async def job_morning_message():
    """Gửi thông báo buổi sáng lúc 6h."""
    try:
        state = get_state()
        if not state["is_on"]:
            return

        now = get_vietnam_time()
        weekday = now.strftime("%A")
        date_str = now.strftime("%d/%m/%Y")

        # Giá USD -> VND
        vnd_rate = await get_usdt_vnd_rate()
        usd_to_vnd = f"{vnd_rate:,.0f}".replace(",", ".") if vnd_rate else "N/A"

        # Xu hướng thị trường
        sentiment = await get_market_sentiment()  # {"long": 65.2, "short": 34.8}

        # Top 5 coin tăng trưởng
        top_coins = await get_top_moving_coins(limit=5)

        # Funding & Volume
        funding_info = await get_market_funding_volume()  # {"funding": "...", "volume": "...", "trend": "..."}

        msg = (
            f"📅 Hôm nay {weekday} — {date_str}\n"
            f"🌞 06:00 — Chào buổi sáng, thị trường hôm nay có những biến động bạn theo dõi nhé\n"
            f"“Chào buổi sáng nhé anh Trương ☀️…”\n\n"
            f"💵 1 USD = {usd_to_vnd} VND\n"
            f"📊 Thị trường nghiêng về: LONG {sentiment['long']:.1f}% | SHORT {sentiment['short']:.1f}%\n\n"
            f"🔥 5 đồng coin nổi bật:\n" +
            "\n".join([f"• {c['symbol']} {c['change_pct']:.2f}%" for c in top_coins]) + "\n\n"
            f"💹 Funding: {funding_info['funding']}\n"
            f"📈 Volume: {funding_info['volume']}\n"
            f"📌 Xu hướng: {funding_info['trend']}\n\n"
            f"⏳ 15 phút nữa sẽ có tín hiệu, bạn cân nhắc vào lệnh nhé!"
        )

        await bot.send_message(chat_id=S.TELEGRAM_ALLOWED_USER_ID, text=msg)

    except Exception as e:
        print(f"[ERROR] job_morning_message: {e}")


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
            f"Kết thúc ngày giao dịch, bạn hãy quản lý tín hiệu tốt.\n"
            f"Chốt lệnh trước khi ngủ để tránh biến động về đêm…\n"
            f"Ngày mai chúng ta sẽ bắt đầu công việc mới!\n\n"
            f"🌙 Chúc anh Trương ngủ ngon 🤗"
        )

        await bot.send_message(chat_id=S.TELEGRAM_ALLOWED_USER_ID, text=msg)

    except Exception as e:
        print(f"[ERROR] job_evening_summary: {e}")
