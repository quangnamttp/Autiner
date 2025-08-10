import asyncio
from datetime import timedelta
from telegram import Bot
from common.time_utils import now_vn, today_slot_dt, seconds_until
from config.settings import SLOT_TIMES, ALLOWED_USER_ID
from features.alerts import countdown_edit
from features.signals import get_batch_text

async def schedule_loop(bot: Bot):
    """Vòng lặp vĩnh viễn chạy theo slot cố định mỗi ngày."""
    while True:
        now = now_vn()
        # Tìm slot kế tiếp trong ngày (hoặc ngày mai)
        next_dt = None
        for hhmm in SLOT_TIMES:
            t = today_slot_dt(hhmm)
            if t > now:
                next_dt = t
                break
        if next_dt is None:
            # Hết ngày -> chuyển qua slot đầu ngày mai
            first = SLOT_TIMES[0]
            next_dt = today_slot_dt(first) + timedelta(days=1)

        # Gửi cảnh báo T-60s
        alert_at = next_dt - timedelta(seconds=60)
        wait1 = seconds_until(alert_at)
        await asyncio.sleep(wait1)

        # Send alert + countdown
        alert_msg = await bot.send_message(
            chat_id=ALLOWED_USER_ID,
            text="⏳ Tín hiệu 30’ tiếp theo – chú ý!\n(Sẽ gửi trong 1 phút nữa)"
        )
        # Chạy countdown song song cho tới mốc
        remain = seconds_until(next_dt)
        await countdown_edit(alert_msg, remain)

        # Đến giờ -> gửi batch 5 tín hiệu
        batch_text = get_batch_text()
        await bot.send_message(chat_id=ALLOWED_USER_ID, text=batch_text)

        # Nghỉ 1 chút để tránh vòng lặp sát biên
        await asyncio.sleep(1)
