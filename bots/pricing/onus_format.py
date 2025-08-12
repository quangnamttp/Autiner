# price_onus.py
# -*- coding: utf-8 -*-
"""
Cách tính giá ONUS cho hiển thị bot/tín hiệu.

- Auto-denom: chuyển các coin siêu nhỏ sang hậu tố 1000/1M giống ONUS
- VND format:
  * Coin mệnh giá nhỏ (…1000 / …1M): giữ 4 số lẻ, ROUND_DOWN (không làm tròn lên)
  * Coin thường: ONUS rule (0/2/4 lẻ) + dấu chấm ngăn nghìn
- USD format: tối đa 4 số lẻ, cắt đuôi 0
"""

from __future__ import annotations
from decimal import Decimal, ROUND_DOWN

SMALL_DENOM_SUFFIXES = ("1M", "1000")

def _round_down(num: float, places: int) -> Decimal:
    q = Decimal("1." + "0"*places) if places > 0 else Decimal("1")
    return Decimal(str(num)).quantize(q, rounding=ROUND_DOWN)

def _thousand_dot(s: str) -> str:
    # đổi ',' → '.' cho đúng kiểu VN
    return s.replace(",", ".")

def is_small_denom_name(name: str) -> bool:
    return any(name.endswith(suf) for suf in SMALL_DENOM_SUFFIXES)

def auto_denom(symbol: str, last_usd: float, vnd_rate: float) -> tuple[str, float, float]:
    """
    Trả về: (display_name, adjusted_usd, multiplier)
    - Nếu giá * VND < 0.001 → nhân 1_000_000, thêm '1M'
    - Nếu giá * VND < 1     → nhân 1_000,     thêm '1000'
    - Ngược lại giữ nguyên
    """
    base = (last_usd or 0.0) * (vnd_rate or 0.0)
    root = str(symbol).replace("_USDT", "")
    if base < 0.001:
        return f"{root}1M", (last_usd or 0.0) * 1_000_000.0, 1_000_000.0
    if base < 1.0:
        return f"{root}1000", (last_usd or 0.0) * 1_000.0, 1_000.0
    return root, float(last_usd or 0.0), 1.0

def fmt_usd(val_usd: float) -> str:
    s = f"{float(val_usd or 0.0):.4f}".rstrip("0").rstrip(".")
    return s if s else "0"

def fmt_vnd_onus(val_vnd: float, small_denom: bool) -> str:
    """
    Format VND theo ONUS:
      - small_denom: 4 lẻ, ROUND_DOWN
      - normal: >=100k:0 lẻ | >=1k:2 lẻ | <1k:4 lẻ (ROUND_DOWN)
    """
    x = float(val_vnd or 0.0)
    if small_denom:
        q = _round_down(x, 4)
        s = f"{q:,.4f}"  # giữ 4 lẻ
        return _thousand_dot(s)
    # coin thường
    if x >= 100_000:
        s = f"{int(x):,}"
        return _thousand_dot(s)
    elif x >= 1_000:
        q = _round_down(x, 2)
        s = f"{q:,.2f}"
        return _thousand_dot(s)
    else:
        q = _round_down(x, 4)
        s = f"{q:,.4f}"
        return _thousand_dot(s)

def onus_display_price(symbol: str, last_usd: float, vnd_rate: float, unit: str = "VND") -> tuple[str, str, float]:
    """
    Tính tên hiển thị & giá hiển thị theo ONUS.
    Trả: (display_name, price_str, adjusted_usd)
    - adjusted_usd: giá USD sau auto-denom (để dùng nhất quán trong thuật toán)
    """
    disp, adj_usd, _ = auto_denom(symbol, last_usd, vnd_rate)
    if unit.upper() == "USD":
        return disp, fmt_usd(adj_usd), adj_usd
    # VND
    small = is_small_denom_name(disp)
    price_vnd = adj_usd * (vnd_rate or 0.0)
    return disp, fmt_vnd_onus(price_vnd, small), adj_usd
