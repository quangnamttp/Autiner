# price_onus.py
# -*- coding: utf-8 -*-
from __future__ import annotations
from decimal import Decimal, ROUND_DOWN

SMALL_DENOM_SUFFIXES = ("1M", "1000")

def _rd(x: float, n: int) -> Decimal:
    q = Decimal("1." + "0"*n) if n>0 else Decimal("1")
    return Decimal(str(x)).quantize(q, rounding=ROUND_DOWN)

def _dot(s: str) -> str:
    return s.replace(",", ".")

def is_small_name(name: str) -> bool:
    return any(str(name).endswith(s) for s in SMALL_DENOM_SUFFIXES)

def auto_denom(symbol: str, last_usd: float, vnd_rate: float) -> tuple[str, float]:
    """
    Trả về (display_name, adjusted_usd).
    Quy tắc ONUS:
    - Nếu last_usd * vnd_rate < 0.001  -> thêm '1M',  nhân 1_000_000
    - elif last_usd * vnd_rate < 1     -> thêm '1000', nhân 1_000
    - else giữ nguyên
    """
    root = str(symbol).replace("_USDT", "")
    base_vnd = (last_usd or 0.0) * (vnd_rate or 0.0)
    if base_vnd < 0.001:
        return f"{root}1M",  (last_usd or 0.0) * 1_000_000.0
    if base_vnd < 1.0:
        return f"{root}1000", (last_usd or 0.0) * 1_000.0
    return root, float(last_usd or 0.0)

def fmt_usd_onus(val_usd: float, small: bool) -> str:
    """
    USD:
    - >= 1_000: không thập phân, chấm ngăn nghìn (VD: 110.232.000)
    - 1 .. <1000: 2 lẻ, ROUND_DOWN
    - < 1: 7 lẻ (không làm tròn) — hợp coin nhỏ như PEPE1000
    """
    x = float(val_usd or 0.0)
    if x >= 1_000:
        return _dot(f"{int(x):,}")
    if x >= 1:
        return _dot(f"{_rd(x,2):,.2f}")
    # nhỏ hơn 1
    return f"{_rd(x,7):f}".rstrip("0").rstrip(".")  # để đúng kiểu 0.0111993

def fmt_vnd_onus(val_vnd: float, small: bool) -> str:
    """
    VND:
    - small (…1000/…1M): 4 lẻ, ROUND_DOWN  (VD: 268.7316)
    - normal: >=100k:0 lẻ | >=1k:2 lẻ | <1k:4 lẻ (đều ROUND_DOWN), chấm ngăn nghìn
    """
    x = float(val_vnd or 0.0)
    if small:
        return _dot(f"{_rd(x,4):,.4f}")
    if x >= 100_000:
        return _dot(f"{int(x):,}")
    if x >= 1_000:
        return _dot(f"{_rd(x,2):,.2f}")
    return _dot(f"{_rd(x,4):,.4f}")

def display_price(symbol: str, last_usd: float, vnd_rate: float, unit: str="VND") -> tuple[str, str]:
    """
    Tính tên hiển thị & giá hiển thị.
    - last_usd: giá **gốc** của MEXC Futures (chưa auto‑denom)
    - Trả về (display_name, price_str)
    """
    name, adj_usd = auto_denom(symbol, last_usd, vnd_rate)
    small = is_small_name(name)
    if unit.upper() == "USD":
        return name, fmt_usd_onus(adj_usd, small)
    return name, fmt_vnd_onus(adj_usd * (vnd_rate or 0.0), small)
