import asyncio
from telegram import Message
from common.time_utils import seconds_until
from common.time_utils import now_vn

def progress_bar(percent: float, width=20) -> str:
    filled = int(round(percent * width))
    return "█" * filled + "░" * (width - filled)

async def countdown_edit(msg: Message, seconds: int):
    total = max(1, seconds)
    # Cập nhật mỗi 5s, 5s cuối mỗi 1s
    step = 5
    remain = total
    try:
        while remain > 0:
            if remain <= 5:
                step = 1
            pct = (total - remain) / total
            bar = progress_bar(pct)
            mm = remain // 60
            ss = remain % 60
            text = (
                "⏳ Tín hiệu 30’ tiếp theo – chú ý!\n"
                "Bot sẽ gửi 5 lệnh (3 Scalping + 2 Swing) ngay sau tin này.\n\n"
                f"Đếm ngược: {mm:02d}:{ss:02d}\n{bar} {int(pct*100)}%"
            )
            await msg.edit_text(text)
            await asyncio.sleep(step)
            remain -= step
    except Exception:
        # Nếu lỗi edit (rate limit, mạng...), bỏ qua để không cản trở việc gửi tín hiệu
        pass
