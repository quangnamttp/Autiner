# -*- coding: utf-8 -*-
from datetime import date, timedelta

try:
    from lunardate import LunarDate
    HAS_LUNAR = True
except Exception:
    HAS_LUNAR = False

VN_WEEK = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]

def _lunar_day_str(g: date) -> str:
    if not HAS_LUNAR:
        return "--/--"
    try:
        ld = LunarDate.fromSolarDate(g.year, g.month, g.day)
        return f"{ld.day}/{ld.month}"  # ví dụ: 8/6
    except Exception:
        return "--/--"

def calendar_month_html(target: date) -> str:
    """
    Xuất lịch tháng dạng HTML (dùng cho Telegram ParseMode.HTML):
    - Tiêu đề: THÁNG mm/yyyy
    - 7 cột T2..CN
    - Mỗi ô 2 dòng (dương in đậm, âm thường), canh thẳng bằng <pre>.
    """
    first = target.replace(day=1)
    pad = first.weekday()  # Mon=0..Sun=6 (cột bắt đầu từ T2)

    # Tính số ngày trong tháng
    if first.month == 12:
        next_first = first.replace(year=first.year + 1, month=1, day=1)
    else:
        next_first = first.replace(month=first.month + 1, day=1)
    last_day = (next_first - timedelta(days=1)).day

    # Header hiển thị
    head = f"📅 THÁNG {first.month:02d}/{first.year}\n" + " ".join([f"{w:^6}" for w in VN_WEEK])

    # Xây cells
    cells = [" " * 6] * pad
    for d in range(1, last_day + 1):
        g = first.replace(day=d)
        dduong = f"<b>{d:02d}</b>"
        dam = _lunar_day_str(g)
        # mỗi ô rộng 7 ký tự, 2 dòng ghép lại bằng ký tự \n trong <pre>
        cell = f"{dduong}\n{dam:>6}"
        cells.append(cell)

    # Ghép thành 6 hàng tối đa, mỗi ô căn trái rộng 8 để có khoảng cách
    rows = []
    for i in range(0, len(cells), 7):
        row = cells[i:i+7]
        rows.append("  ".join(f"{c:<8}" for c in row))

    body = "\n".join(rows)

    # Dùng <pre> để giữ khoảng trắng cố định
    html = f"{head}\n<pre>{body}</pre>"
    return html
