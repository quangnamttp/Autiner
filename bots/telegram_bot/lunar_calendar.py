# -*- coding: utf-8 -*-
from datetime import date, timedelta
from lunardate import LunarDate

VN_WEEK = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]

def _lunar_day_str(g: date) -> str:
    try:
        ld = LunarDate.fromSolarDate(g.year, g.month, g.day)
        # ví dụ: 8/6 (mùng 8 tháng 6 âm)
        return f"{ld.day}/{ld.month}"
    except Exception:
        return "--/--"

def calendar_month_text(target: date) -> str:
    """
    Trả về lịch tháng dạng text:
    - Tiêu đề: THÁNG mm/yyyy
    - 7 cột T2..CN
    - Mỗi ô: dương **DD** + dòng dưới âm dd/mm
    """
    first = target.replace(day=1)
    # thứ trong tuần (Mon=0..Sun=6) → muốn cột bắt đầu từ T2 (Mon)
    pad = first.weekday()  # 0..6

    # số ngày trong tháng
    if first.month == 12:
        next_first = first.replace(year=first.year + 1, month=1, day=1)
    else:
        next_first = first.replace(month=first.month + 1, day=1)
    last_day = (next_first - timedelta(days=1)).day

    # header
    lines = []
    lines.append(f"📅 THÁNG {first.month:02d}/{first.year}")
    lines.append(" ".join([f"{w:^6}" for w in VN_WEEK]))

    # build cells (6 hàng tối đa)
    cells = ["      "] * pad
    for d in range(1, last_day + 1):
        g = first.replace(day=d)
        dduong = f"**{d:02d}**"  # in đậm ngày dương
        dam = _lunar_day_str(g)
        cell = f"{dduong}\n{dam:>6}"
        cells.append(cell)

    # nhóm 7 cột
    for i in range(0, len(cells), 7):
        row = cells[i:i+7]
        # căn mỗi ô bề rộng 8 ký tự, tách bằng 2 khoảng trắng
        lines.append("  ".join(f"{c:<8}" for c in row))

    return "\n".join(lines)
