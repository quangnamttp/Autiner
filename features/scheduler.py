import asyncio
from datetime import timedelta
from telegram import Bot
from common.time_utils import now_vn, today_slot_dt, seconds_until
from config.settings import SLOT_TIMES, ALLOWED_USER_ID
from features.alerts import countdown_edit
from features.signals import get_batch_messages

async def schedule_loop(bot: Bot):
    """Vòng lặp vĩnh viễn chạy theo slot cố định mỗi ngày."""
    while True:
        now = now_vn()
        next_dt = None
        for hhmm in SLOT_TIMES:
            t = today_slot_dt(hhmm)
            if t > now:
                next_dt = t
                break
        if next_dt is None:
            first = SLOT_TIMES[0]
            next_dt = today_slot_dt(first) + timedelta(days=1)

        # Gửi cảnh báo T-60s
        alert_at = next_dt - timedelta(seconds=60)
        await asyncio.sleep(seconds_until(alert_at))

        # Tin cảnh báo + đếm ngược
        alert_msg = await bot.send_message(
            chat_id=ALLOWED_USER_ID,
            text="⏳ Tín hiệu 30’ tiếp theo – chú ý!\n(Sẽ gửi trong 1 phút nữa)"
        )
        await countdown_edit(alert_msg, seconds_until(next_dt))

        # Đến giờ -> gửi 5 tín hiệu, MỖI TÍN HIỆU MỘT TIN NHẮN
        msgs = get_batch_messages()
        for m in msgs:
            await bot.send_message(chat_id=ALLOWED_USER_ID, text=m)
            await asyncio.sleep(1.2)  # giãn cách nhẹ để tránh spam API

        await asyncio.sleep(1)
