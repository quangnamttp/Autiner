# autiner/bots/pricing/night_summary.py
from datetime import datetime

def build_night_summary(date: datetime, stats: dict):
    lines = [f"🌙 Tổng kết phiên {date:%d/%m/%Y}"]
    lines.append(f"✅ Tỷ lệ TP: {stats.get('tp',0)}% | ❌ Tỷ lệ SL: {stats.get('sl',0)}%")
    lines.append(f"📊 MUA: {stats.get('buy',0)}% | BÁN: {stats.get('sell',0)}%")
    lines.append("\nChúc bạn ngủ ngon 😴")
    return "\n".join(lines)
