# autiner/bots/pricing/night_summary.py
# -*- coding: utf-8 -*-
"""
Tổng kết cuối ngày (22:00).
- Không liệt kê top 5.
- Tính thiên hướng thị trường từ snapshot MEXC (volume-weighted).
- An toàn: nếu nguồn chậm/ lỗi -> fallback trung tính.
- Trả về TEXT (Markdown) để bot gửi.
"""

from __future__ import annotations
from datetime import datetime
import pytz

from settings import TZ_NAME
# Đồng bộ nguồn với Signal Engine (đang dùng trong bot)
from bots.signals.signal_engine import market_snapshot

VN_TZ = pytz.timezone(TZ_NAME)

def _weekday_vi(dt: datetime) -> str:
    names = ["Thứ Hai","Thứ Ba","Thứ Tư","Thứ Năm","Thứ Sáu","Thứ Bảy","Chủ Nhật"]
    return names[dt.weekday()]

def _bias_from_snapshot() -> tuple[str, int, int]:
    """
    Lấy thiên hướng từ % thay đổi 24h, trọng số theo volumeQuote.
    Trả: (bias_txt, long_pct, short_pct)
    """
    try:
        coins, live, _ = market_snapshot(unit="USD", topn=40)
        if not live or not coins:
            raise RuntimeError("snapshot not live")

        tot = 0.0
        long_w = 0.0
        for c in coins:
            vol = float(c.get("volumeQuote", 0.0)) or 0.0
            chg = float(c.get("change24h_pct", 0.0)) or 0.0
            w = max(1.0, vol)  # chống 0
            tot += w
            if chg > 0:
                long_w += w

        if tot <= 0:
            raise RuntimeError("zero total vol")

        long_pct = int(round(long_w / tot * 100))
        short_pct = 100 - long_pct

        if   long_pct >= 60: bias = "tăng giá"
        elif short_pct >= 60: bias = "giảm giá"
        elif 53 <= long_pct < 60: bias = "tăng giá nhẹ"
        else: bias = "trung tính"

        return bias, long_pct, short_pct

    except Exception:
        # fallback an toàn
        return "trung tính", 50, 50

def build_night_message(username: str | None = None) -> str:
    """
    Tạo nội dung tổng kết 22:00 (Markdown).
    Dùng trong telegram_bot: _send_22h()
    """
    now = datetime.now(VN_TZ)
    bias_txt, lp, sp = _bias_from_snapshot()

    header_date = f"📅 {_weekday_vi(now)}, {now.strftime('%d/%m/%Y')}"
    hi = "🌙 22:00 — Tổng kết ngày"
    if username:
        hi += f" | Chúc {username} ngủ ngon"

    lines = [
        header_date,
        hi,
        "",
        "📈 Thị trường hôm nay:",
        f"- Xu hướng chủ đạo: **{bias_txt}**",
        f"- Long {lp}% | Short {sp}%",
        "",
        "💡 Nhận định:",
        "Giữ nhịp ổn định. Nếu vị thế trong ngày đã đạt mục tiêu, nên chốt bớt; phần còn lại dùng trailing stop.",
        "",
        "😴 Hẹn gặp bạn lúc **06:00** ngày mai để cập nhật sớm và vào nhịp mới.",
    ]
    return "\n".join(lines)
