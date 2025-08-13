# Autiner/bots/pricing/night_summary.py
# -*- coding: utf-8 -*-
"""
Gửi tổng kết cuối ngày 22:00 (đơn giản, chuyên nghiệp).
- Không liệt kê top 5.
- Tính thiên hướng thị trường (Long/Short) từ snapshot MEXC.
- An toàn: nếu nguồn chậm -> dùng fallback tĩnh.
"""

from __future__ import annotations
from datetime import datetime, time as dt_time
import pytz
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, Application

from settings import TZ_NAME, ALLOWED_USER_ID
# 🔁 Đồng bộ nguồn dữ liệu với Signal Engine
from ..signals.signal_engine import market_snapshot

VN_TZ = pytz.timezone(TZ_NAME)

def _weekday_vi(dt: datetime) -> str:
    names = ["Thứ Hai","Thứ Ba","Thứ Tư","Thứ Năm","Thứ Sáu","Thứ Bảy","Chủ Nhật"]
    return names[dt.weekday()]

def _bias_from_snapshot() -> tuple[str, int, int]:
    """Trả: (bias_txt, long_pct, short_pct)"""
    try:
        coins, live, _ = market_snapshot(unit="USD", topn=40)
        if not live or not coins:
            raise RuntimeError("no live data")
        tot = sum(max(1.0, float(c.get("volumeQuote", 0.0))) for c in coins)
        long_w = sum(max(1.0, float(c.get("volumeQuote", 0.0)))
                     for c in coins if float(c.get("change24h_pct", 0.0)) > 0)
        short_w = tot - long_w
        long_pct = int(round(long_w / tot * 100))
        short_pct = 100 - long_pct
        bias_txt = ("tăng giá nhẹ" if 53 <= long_pct < 60 else
                    "tăng giá" if long_pct >= 60 else
                    "giảm giá" if short_pct >= 60 else
                    "trung tính")
        return bias_txt, long_pct, short_pct
    except Exception:
        return "trung tính", 50, 50

def build_night_message(username: str | None = None) -> str:
    now = datetime.now(VN_TZ)
    bias_txt, lp, sp = _bias_from_snapshot()
    header_date = f"📅 {_weekday_vi(now)}, {now.strftime('%d/%m/%Y')}"
    hi = f"🌙 22:00 — Tổng kết ngày" + (f" | Chúc {username} ngủ ngon" if username else "")
    lines = [
        header_date,
        hi,
        "",
        "📈 Thị trường hôm nay:",
        f"- Xu hướng chủ đạo: **{bias_txt}**",
        f"- Long {lp}% | Short {sp}%",
        "",
        "💡 Nhận định:",
        "Giữ nhịp ổn
