# Autiner/bots/pricing/morning_report.py
# -*- coding: utf-8 -*-
"""
Bản tin 06:00 — Chào buổi sáng (MEXC Futures)

• Lấy USD/VND
• Lấy danh sách futures: symbol, lastPrice, quoteVol (24h), %change
• Chọn Top 5 theo volume 24h
• Áp dụng định dạng giá ONUS từ onus_format.display_price (bạn đã có)
• Ước tính thiên hướng thị trường (Long/Short) theo %change24h có trọng số volume
• Trả về text để bot gửi, hoặc dùng hàm async để lên lịch 06:00
"""

from __future__ import annotations
from typing import List, Dict, Tuple
from datetime import datetime, time as dt_time
import requests
import pytz

from settings import (
    USDVND_URL, MEXC_TICKER_URL, DEFAULT_UNIT, TZ_NAME,
    TELEGRAM_BOT_TOKEN, ALLOWED_USER_ID
)

# ⚠️ Bạn đã có file này rồi:
# Autiner/bots/pricing/onus_format.py  (chỉ import dùng, không chỉnh ở đây)
from .onus_format import display_price  # (display_name, price_str) = display_price(symbol, last_usd, vnd_rate, unit)

VN_TZ = pytz.timezone(TZ_NAME)
_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124 Safari/537.36"}
HTTP_TIMEOUT = 10


# -------- helpers --------
def _get_json(url: str):
    try:
        r = requests.get(url, headers=_HEADERS, timeout=HTTP_TIMEOUT)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None

def get_usd_vnd_rate() -> float:
    js = _get_json(USDVND_URL)
    try:
        return float(js.get("rates", {}).get("VND", 0.0)) if isinstance(js, dict) else 0.0
    except Exception:
        return 0.0

def fetch_mexc_tickers() -> List[Dict]:
    """
    Chuẩn hóa tối thiểu:
    [{symbol:"BTC_USDT", last:<float>, qv:<float>, chg:<percent>}, ...]
    """
    js = _get_json(MEXC_TICKER_URL)
    out = []
    rows = []
    if isinstance(js, dict) and (js.get("success") or "data" in js):
        rows = js.get("data") or []
    elif isinstance(js, list):
        rows = js

    for it in rows:
        sym = it.get("symbol") or it.get("instrument_id")
        if not sym or not str(sym).endswith("_USDT"):
            continue
        # last
        try:
            last = float(it.get("lastPrice") or it.get("last") or it.get("price") or it.get("close") or 0.0)
        except:
            last = 0.0
        # quoteVol 24h (USDT)
        try:
            qv = float(it.get("quoteVol") or it.get("amount24") or it.get("turnover") or it.get("turnover24") or 0.0)
        except:
            qv = 0.0
        # % change 24h -> chuẩn hóa về %
        try:
            raw = it.get("riseFallRate") or it.get("changeRate") or it.get("percent") or 0
            chg = float(raw)
            if abs(chg) < 1.0:
                chg *= 100.0
        except:
            chg = 0.0

        out.append({"symbol": str(sym), "last": last, "qv": qv, "chg": chg})
    return out

def pick_top5_by_volume(items: List[Dict]) -> List[Dict]:
    return sorted(items, key=lambda d: d.get("qv", 0.0), reverse=True)[:5]

def market_bias(items: List[Dict], topn: int = 40) -> Tuple[float, float, str]:
    """
    Ước tính thiên hướng: dùng top N theo volume.
    Tính tỉ trọng dương/âm theo volume (weight).
    """
    pool = sorted(items, key=lambda d: d.get("qv", 0.0), reverse=True)[:max(10, topn)]
    pos_w = sum(d["qv"] for d in pool if d.get("chg", 0.0) > 0)
    neg_w = sum(d["qv"] for d in pool if d.get("chg", 0.0) < 0)
    total = pos_w + neg_w
    if total <= 0:
        return 50.0, 50.0, "Trung tính"
    long_pct = round(pos_w / total * 100.0)
    short_pct = 100 - long_pct
    bias = "Thiên Long" if long_pct > short_pct else ("Thiên Short" if short_pct > long_pct else "Trung tính")
    return float(long_pct), float(short_pct), bias

def arrow_and_sign(change_pct: float) -> Tuple[str, str]:
    """Trả (emoji mũi tên, chuỗi % có dấu)."""
    if change_pct >= 0:
        return "🔺", f"+{change_pct:.2f}%"
    return "🔻", f"{change_pct:.2f}%"

def fmt_vnd_rate(v: float) -> str:
    # 25,123.45
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def weekday_vi(dt: datetime) -> str:
    names = ["Thứ Hai","Thứ Ba","Thứ Tư","Thứ Năm","Thứ Sáu","Thứ Bảy","Chủ Nhật"]
    return names[dt.weekday()]


# -------- public: build text --------
def build_morning_text(unit: str | None = None, recipient_name: str | None = None) -> str:
    """
    Trả về chuỗi tin nhắn 06:00 (không gửi).
    • unit: 'VND' | 'USD' (mặc định lấy từ DEFAULT_UNIT)
    • recipient_name: tên người nhận (hiển thị trong lời chào)
    """
    unit = (unit or DEFAULT_UNIT or "VND").upper()
    now = datetime.now(VN_TZ)
    usd_vnd = get_usd_vnd_rate()
    tickers = fetch_mexc_tickers()

    # thiên hướng
    long_pct, short_pct, bias = market_bias(tickers, topn=40)

    # top 5 theo volume
    top5 = pick_top5_by_volume(tickers)

    # header
    head_day = f"📅 {weekday_vi(now)}, {now.strftime('%d/%m/%Y')}"
    hello = f"🌞 06:00 — Chào buổi sáng{' anh ' + recipient_name if recipient_name else ''}! ☀️"
    rate_line = f"💵 1 USD ≈ {fmt_vnd_rate(usd_vnd)} VND"
    bias_line = f"📈 Thiên hướng thị trường: {bias} (Long {long_pct:.0f}% | Short {short_pct:.0f}%)"

    # danh sách top 5
    lines = []
    for i, d in enumerate(top5, 1):
        disp, price = display_price(d["symbol"], d["last"], usd_vnd, unit)
        arrow, pct = arrow_and_sign(float(d.get("chg", 0.0)))
        lines.append(f"{i}. {disp} — {price} {unit}  {arrow} {pct}")

    coins_block = "🔝 Top 5 theo khối lượng 24h (MEXC Futures — theo " + unit + "):\n" + "\n".join(lines)

    warn = (
        "⚠️ Cảnh báo xu hướng hôm nay: Nghiêng theo thiên hướng ở trên; "
        "tránh đu nến khi biến động > 1.5×ATR(5m), ưu tiên vào lại vùng hồi theo xu hướng."
    )
    next_info = "⏱️ 15 phút tới sẽ có tín hiệu đầu tiên. Chuẩn bị sẵn sàng nhé!"

    return "\n".join([head_day, hello, rate_line, "", bias_line, "", coins_block, "", warn, next_info])


# -------- optional: Telegram job --------
async def send_morning_report(context, unit: str | None = None, recipient_name: str | None = None):
    """
    Dùng với JobQueue:
        j.run_daily(send_morning_report, time=dt_time(6,0,tzinfo=VN_TZ))
    """
    chat_id = ALLOWED_USER_ID
    text = build_morning_text(unit=unit, recipient_name=recipient_name)
    await context.bot.send_message(chat_id, text)

def schedule_morning_job(app, name: str | None = None, unit: str | None = None):
    """Gọi trong build_app() nếu muốn lên lịch cố định 06:00 VN time."""
    j = app.job_queue
    j.run_daily(
        send_morning_report,
        time=dt_time(6, 0, tzinfo=VN_TZ),
        data={"unit": unit, "name": name},
        name="morning_report_06h"
    )
