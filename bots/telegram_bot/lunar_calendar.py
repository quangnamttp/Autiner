# -*- coding: utf-8 -*-
"""
Lunar calendar (Âm/Dương) dạng HTML cho Telegram.

- Hiển thị theo THÁNG.
- Dòng đầu: tiêu đề "THÁNG mm/yyyy".
- Dòng kế: tiêu đề cột T2..CN.
- Mỗi tuần gồm 2 dòng:
    + Dòng 1: ngày dương (in đậm) của 7 ô.
    + Dòng 2: ngày âm tương ứng (dd/mm âm lịch).
- Dùng <pre> để giữ nguyên khoảng cách cố định (monospace).
- Không dùng màu; ngày dương in đậm qua <b>..</b>.

Yêu cầu: lunardate==0.2.0 trong requirements.txt
"""

from __future__ import annotations
from datetime import date, timedelta
from typing import List

from lunardate import LunarDate

VN_WEEK = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]

# độ rộng mỗi ô (khoảng trắng trong font monospace)
CELL_W = 8  # đủ để hiển thị "**DD**" và "dd/mm"

def _lunar_str(g: date) -> str:
    """Trả về 'dd/mm' âm lịch cho ngày dương g."""
    try:
        ld = LunarDate.fromSolarDate(g.year, g.month, g.day)
        return f"{ld.day:02d}/{ld.month:02d}"
    except Exception:
        return "--/--"

def _bold_dd(d: int) -> str:
    """Ngày dương in đậm 2 chữ số."""
    return f"<b>{d:02d}</b>"

def _pad(s: str, width: int = CELL_W) -> str:
    """Căn trái chuỗi trong ô cố định."""
    if len(s) >= width:
        return s[:width]
    return s + " " * (width - len(s))

def _center(s: str, width: int) -> str:
    if len(s) >= width:
        return s[:width]
    left = (width - len(s)) // 2
    right = width - len(s) - left
    return " " * left + s + " " * right

def _month_range(d: date) -> int:
    """Số ngày trong tháng của 'd'."""
    first = d.replace(day=1)
    if first.month == 12:
        next_first = first.replace(year=first.year + 1, month=1, day=1)
    else:
        next_first = first.replace(month=first.month + 1, day=1)
    return (next_first - timedelta(days=1)).day

def calendar_month_html(target: date) -> str:
    """
    Trả về HTML để gửi vào Telegram (ParseMode.HTML).
    Ví dụ sử dụng:
        html = calendar_month_html(date.today())
        bot.send_message(chat_id, html, parse_mode=ParseMode.HTML)
    """
    first = target.replace(day=1)
    last_day = _month_range(target)

    # Monday=0..Sunday=6; cột bắt đầu từ T2 (Mon)
    start_pad = first.weekday()  # số ô trống đầu tuần đầu tiên

    title = f"THÁNG {first.month:02d}/{first.year}"
    # 7 cột, mỗi cột CELL_W ký tự -> tổng chiều rộng
    total_w = CELL_W * 7
    lines: List[str] = []
    lines.append(_center(title, total_w))
    lines.append("".join(_pad(_center(w, CELL_W), CELL_W) for w in VN_WEEK))

    # tạo danh sách từng ô (None = ô trống trước ngày 1)
    boxes: List[date | None] = [None] * start_pad
    for d in range(1, last_day + 1):
        boxes.append(first.replace(day=d))

    # đệm cho đủ bội số 7
    while len(boxes) % 7 != 0:
        boxes.append(None)

    # in theo tuần; mỗi tuần in 2 dòng (dương / âm)
    for i in range(0, len(boxes), 7):
        week = boxes[i : i + 7]
        row_duong = []
        row_am = []
        for cell in week:
            if cell is None:
                row_duong.append(_pad(""))
                row_am.append(_pad(""))
            else:
                row_duong.append(_pad(_bold_dd(cell.day)))
                row_am.append(_pad(_lunar_str(cell)))
        lines.append("".join(row_duong))
        lines.append("".join(row_am))

    # gói trong <pre> để giữ monospace
    return "<pre>" + "\n".join(lines) + "</pre>"
