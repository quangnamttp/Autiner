# -*- coding: utf-8 -*-
"""
Công thức giá ONUS (áp dụng cho hiển thị MEXC VND và tín hiệu):
- Quy đổi ONUS auto-denom cho coin mệnh giá siêu nhỏ:
    base_vnd = last_usd * vnd_rate
    if base_vnd < 0.001  -> nhân 1_000_000  (hậu tố '1M')    # ví dụ PEPE1M
    elif base_vnd < 1    -> nhân 1_000      (hậu tố '1000')  # ví dụ BONK1000
    else                  giữ nguyên                          # BTC, ETH, ...
- Format VND giống ONUS (ROUND_DOWN, phân tách nghìn bằng dấu chấm):
    >= 100_000 VND : 0 số lẻ
    >=   1_000 VND : 2 số lẻ
    <    1_000 VND : 4 số lẻ
- Không làm tròn lên: luôn cắt bớt (ROUND_DOWN).
"""

from __future__ import annotations
from decimal import Decimal, ROUND_DOWN
from typing import Tuple

# ---------- Format helpers ----------

def _group_thousands_dot(s: str) -> str:
    """Đổi dấu phẩy chuẩn US -> dấu chấm ngăn nghìn theo VN."""
    return s.replace(",", ".")

def format_onus_vnd(value_vnd: float | int) -> str:
    """
    Format số tiền VND theo quy tắc ONUS (ROUND_DOWN, 0/2/4 số lẻ).
    Ví dụ:
      2294907318  -> '2.294.907.318'
      92351038.5  -> '92.351.038,50'  (nhưng dùng dấu chấm nên -> '92.351.038.50')
    Lưu ý: theo đặc tả trước giờ ta dùng dấu '.' cho cả nghìn và thập phân.
    """
    val = Decimal(str(value_vnd or 0.0))
    if val >= Decimal("100000"):
        q = val.quantize(Decimal("1"), rounding=ROUND_DOWN)                 # 0 lẻ
        s = f"{int(q):,}"
    elif val >= Decimal("1000"):
        q = val.quantize(Decimal("0.01"), rounding=ROUND_DOWN)              # 2 lẻ
        s = f"{q:,.2f}"
    else:
        q = val.quantize(Decimal("0.0001"), rounding=ROUND_DOWN)            # 4 lẻ
        s = f"{q:,.4f}"
    return _group_thousands_dot(s)

# ---------- Auto-denom (ONUS-style) ----------

def auto_denom(symbol: str, last_usd: float, vnd_rate: float) -> Tuple[str, float, float]:
    """
    Tự động “phóng to” đơn vị hiển thị cho coin siêu nhỏ (ONUS-style).
    Trả về:
        display_symbol : tên để hiển thị (thêm '1000' hoặc '1M' khi cần)
        adjusted_usd   : giá USD sau khi nhân hệ số (để tính toán nhất quán)
        multiplier     : hệ số đã nhân (1 / 1_000 / 1_000_000)
    """
    base_vnd = float(last_usd or 0.0) * float(vnd_rate or 0.0)
    root = str(symbol or "").replace("_USDT", "")

    if base_vnd < 0.001:
        mul = 1_000_000.0
        disp = f"{root}1M"
    elif base_vnd < 1.0:
        mul = 1_000.0
        disp = f"{root}1000"
    else:
        mul = 1.0
        disp = root
    return disp, float(last_usd or 0.0) * mul, mul

# ---------- API gói gọn để dùng một dòng ----------

def price_vnd_onus(symbol: str, last_usd: float, vnd_rate: float) -> Tuple[str, float, float, str]:
    """
    Gộp: auto_denom + quy đổi VND + format ONUS.
    Trả:
        display_symbol, raw_vnd, multiplier, formatted_vnd
    """
    disp, adj_usd, mul = auto_denom(symbol, last_usd, vnd_rate)
    raw_vnd = float(adj_usd) * float(vnd_rate or 0.0)
    return disp, raw_vnd, mul, format_onus_vnd(raw_vnd)

# ---------- Phụ trợ hiển thị % với mũi tên màu ----------
def arrow_pct(pct: float) -> str:
    """
    Trả text phần trăm với mũi tên màu (🔺 xanh / 🔻 đỏ), 2 số lẻ.
    Ví dụ: +2.15% -> '🔺 +2.15%' ; -0.85% -> '🔻 -0.85%'
    """
    try:
        p = float(pct or 0.0)
    except Exception:
        p = 0.0
    sign = "+" if p >= 0 else ""
    arrow = "🔺" if p >= 0 else "🔻"
    return f"{arrow} {sign}{abs(p):.2f}%"
