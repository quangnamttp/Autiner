# autiner/bots/pricing/morning_report.py
# -*- coding: utf-8 -*-
"""
Bản tin 06:00 — Chào buổi sáng (MEXC Futures)

• Lấy USD/VND
• Lấy danh sách futures: symbol, lastPrice, quoteVol (24h), %change
• Chọn Top 5 theo volume 24h
• Định dạng giá theo ONUS (display_price)
• Ước tính thiên hướng thị trường (Long/Short) theo %change24h có trọng số volume
• Trả về text cho Telegram bot (không tự schedule trong file này)
"""

from __future__ import annotations
from typing import List, Dict, Tuple
from datetime import datetime
import requests
import pytz

from settings import USDVND_URL, MEXC_TICKER_URL, DEFAULT_UNIT, TZ_NAME

# Formatter ONUS (đúng đường dẫn repo hiện tại)
from bots.pricing.onus_format import display_price  # -> (display_name, price_str)

VN_TZ = pytz.timezone(TZ_NAME)
_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124 Safari/537.36"}
HTTP_TIMEOUT = 10


# ---------------- helpers ----------------
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
    out: List[Dict] = []
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
        except Exception:
            last = 0.0
        # quoteVol 24h (USDT) — vá nhiều khóa có thể gặp
        qv = 0.0
        for k in ("quoteVol", "amount24", "turnover", "turnover24", "turnover24h",
                  "quote_volume", "volValue", "volQuote", "volumeQuote"):
            if isinstance(it, dict) and k in it and it[k] not in (None, "", "0"):
                try:
                    qv = float(it[k]); break
                except Exception:
                    pass
        if qv == 0.0:
            for k in ("volume24", "vol24", "baseVol", "volume"):
                if k in it and it[k] not in (None, "", "0"):
                    try:
                        base_vol = float(it[k])
                        if base_vol > 0 and last > 0:
                            qv = base_vol * last
                            break
                    except Exception:
                        pass
        # % change 24h -> về %
        try:
            raw = it.get("riseFallRate") or it.get("changeRate") or it.get("percent") or 0
            chg = float(raw)
            if abs(chg) < 1.0:
                chg *= 100.0
        except Exception:
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
    pos_w = sum(d.get("qv", 0.0) for d in pool if d.get("chg", 0.0) > 0)
    neg_w = sum(d.get("qv", 0.0) for d in pool if d.get("chg", 0.0) < 0)
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

def fmt_num(n: float, decimals: int = 0) -> str:
    s = f"{n:,.{decimals}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")

def weekday_vi(dt: datetime) -> str:
    names = ["Thứ Hai","Thứ Ba","Thứ Tư","Thứ Năm","Thứ Sáu","Thứ Bảy","Chủ Nhật"]
    return names[dt.weekday()]


# ---------------- public ----------------
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

    if not tickers:
        hi = f"🌅 06:00 — Chào buổi sáng{(', ' + recipient_name) if recipient_name else ''}!"
        return (
            f"{hi}\n"
            f"⚠️ Không lấy được dữ liệu thị trường lúc {now.strftime('%H:%M %d/%m/%Y')}.\n"
            "Bạn thử /status hoặc /test lại sau nhé."
        )

    long_pct, short_pct, bias = market_bias(tickers, topn=40)
    top5 = pick_top5_by_volume(tickers)

    # Header
    head_day = f"📅 {weekday_vi(now)}, {now.strftime('%d/%m/%Y')}"
    hi = f"🌅 06:00 — Chào buổi sáng" + (f", {recipient_name}!" if recipient_name else "!")
    fx_line = f"💱 USD/VND ≈ {fmt_num(usd_vnd, 2)}"

    # Top 5
    lines = [head_day, hi, fx_line, "", "🔥 Top 5 Futures theo khối lượng 24h:"]
    for it in top5:
        sym = it["symbol"]
        last = float(it.get("last", 0.0))
        qv = float(it.get("qv", 0.0))
        chg = float(it.get("chg", 0.0))
        name, px_txt = display_price(sym, last, usd_vnd, unit)
        arrow, chg_txt = arrow_and_sign(chg)
        vol_txt = fmt_num(qv, 0)
        lines.append(f"• {name}: {px_txt} {unit}  {arrow}{chg_txt}  | Vol24h: {vol_txt} USDT")

    # Bias
    lines += [
        "",
        "🧭 Thiên hướng thị trường (KL trọng số):",
        f"• Long {int(long_pct)}% | Short {int(short_pct)}%  → **{bias}**",
        "",
        "Chúc bạn một ngày giao dịch hiệu quả! ✅"
    ]
    return "\n".join(lines)
