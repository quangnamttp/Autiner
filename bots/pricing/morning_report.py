# autiner/bots/pricing/morning_report.py
from datetime import datetime

def build_morning_report(date: datetime, usd_vnd: float, trend_text: str, top_coins: list):
    lines = [f"🌅 Chào buổi sáng {date:%d/%m/%Y} ☀️",
             f"Tỷ giá USDT/VND hôm nay: {usd_vnd:,.0f}".replace(",", ".") + "₫",
             f"Xu hướng thị trường: {trend_text}"]

    lines.append("\n📈 Top 5 coin nổi bật:")
    for c in top_coins:
        lines.append(f"- {c}")

    return "\n".join(lines)
