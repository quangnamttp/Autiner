import asyncio
from telegram import Message

def progress_bar(percent: float, width=20) -> str:
    filled = int(round(percent * width))
    return "█" * filled + "░" * (width - filled)

async def countdown_edit(msg: Message, seconds: int):
    """Đếm ngược từng giây trước khi gửi tín hiệu."""
    total = max(1, seconds)
    remain = total
    try:
        while remain > 0:
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
            await asyncio.sleep(1)  # Cập nhật mỗi 1 giây
            remain -= 1
    except Exception:
        pass
