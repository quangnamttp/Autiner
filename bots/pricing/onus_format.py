# price_format.py
# -*- coding: utf-8 -*-
"""
Cách tính giá ONUS cho hiển thị bot/tín hiệu.
- Auto‑denom: …1000 / …1M cho coin siêu nhỏ
- Áp tick size theo từng cặp để số lẻ/giá đúng như UI sàn (BONK1000 3 lẻ, SHIB1000 2 lẻ…)
- VND: dùng dấu chấm ngăn nghìn, ROUND_DOWN (không làm tròn lên)
- USD: >=1000 không lẻ; 1.. <1000 2 lẻ; <1 tối đa ~7 lẻ
"""

from __future__ import annotations
from decimal import Decimal, ROUND_DOWN, getcontext

getcontext().prec = 28

SMALL_DENOM_SUFFIXES = ("1M", "1000")

# Ép hậu tố cho vài coin siêu nhỏ để nhất quán (tránh lệch khi rate dao động)
FORCE_DENOM = {
    "PEPE":  "1000",
    "SHIB":  "1000",
    "BONK":  "1000",
    "FLOKI": "1000",
}

# ---------------- core helpers ----------------
def _rd(x: float, n: int) -> Decimal:
    q = Decimal("1." + "0"*n) if n > 0 else Decimal("1")
    return Decimal(str(x)).quantize(q, rounding=ROUND_DOWN)

def _dot(s: str) -> str:
    return s.replace(",", ".")

def is_small_name(name: str) -> bool:
    return any(str(name).endswith(s) for s in SMALL_DENOM_SUFFIXES)

# ---------------- auto-denom (ONUS rule) ----------------
def auto_denom(symbol: str, last_usd: float, vnd_rate: float) -> tuple[str, float, float]:
    """
    Trả (display_name, adjusted_usd, multiplier)
    - Nếu base_vnd < 0.001  -> hậu tố '1M',  * 1_000_000
    - elif base_vnd < 1     -> hậu tố '1000',* 1_000
    - else giữ nguyên
    Ngoài ra ép hậu tố với FORCE_DENOM để nhất quán hiển thị.
    """
    root = str(symbol).replace("_USDT", "")
    if root in FORCE_DENOM:
        tag = FORCE_DENOM[root]
        mul = 1_000_000.0 if tag == "1M" else 1_000.0
        return f"{root}{tag}", (last_usd or 0.0) * mul, mul

    base_vnd = (last_usd or 0.0) * (vnd_rate or 0.0)
    if base_vnd < 0.001:
        return f"{root}1M",  (last_usd or 0.0) * 1_000_000.0, 1_000_000.0
    if base_vnd < 1.0:
        return f"{root}1000", (last_usd or 0.0) * 1_000.0,     1_000.0
    return root, float(last_usd or 0.0), 1.0

# ---------------- format rules (ONUS style) ----------------
def fmt_usd_onus(val_usd: float) -> str:
    x = float(val_usd or 0.0)
    if x >= 1_000:
        return _dot(f"{int(x):,}")               # không thập phân
    if x >= 1:
        return _dot(f"{_rd(x,2):,.2f}")          # 2 lẻ, ROUND_DOWN
    return f"{_rd(x,7):f}".rstrip("0").rstrip(".")  # <1: tối đa ~7 lẻ

def fmt_vnd_onus(val_vnd: float, small: bool, decimals: int | None = None) -> str:
    """
    Nếu truyền decimals (số lẻ) -> định dạng đúng theo tick size.
    Nếu không có decimals -> dùng fallback ONUS: small=4 lẻ; lớn=0 lẻ; vừa=2 lẻ; rất nhỏ=4 lẻ.
    """
    x = float(val_vnd or 0.0)
    if decimals is not None:
        q = _rd(x, decimals)
        return _dot(f"{q:,.{decimals}f}")

    if small:
        return _dot(f"{_rd(x,4):,.4f}")
    if x >= 100_000:
        return _dot(f"{int(x):,}")
    if x >= 1_000:
        return _dot(f"{_rd(x,2):,.2f}")
    return _dot(f"{_rd(x,4):,.4f}")

# ---------------- tick-size layer ----------------
# Tick theo **đơn vị hiển thị** (VND hoặc USD sau auto‑denom)
TICK_VND = {
    # coin mệnh giá nhỏ (đúng như app bạn chụp)
    "PEPE1000": 0.0001,   # 4 lẻ  → 268.7316
    "SHIB1000": 0.01,     # 2 lẻ  → 313.19
    "BONK1000": 0.001,    # 3 lẻ  → 588.312
    "FLOKI1000": 0.01,    # 2 lẻ  → 2,613.84
    # coin vừa/lớn
    "ARC": 0.01,
    "TRUMP": 1,
    "BTC": 1,
    "ETH": 0.01,
}

TICK_USD = {
    "BTC": 1,
    "ETH": 0.01,
    # coin siêu nhỏ sau auto‑denom thường <1 USD -> 7 lẻ là đủ, không cần tick
}

def _infer_tick_vnd(price_vnd: float, small: bool) -> float:
    # fallback nhẹ khi không có trong TICK_VND
    if small:
        return 0.0001 if price_vnd < 10 else 0.01
    if price_vnd >= 100_000:
        return 1.0
    if price_vnd >= 1_000:
        return 0.01
    return 0.0001

def _lookup_tick(name: str, unit: str, price_val: float, small: bool) -> float:
    root = name.replace("1M", "").replace("1000", "")
    if unit.upper() == "VND":
        return TICK_VND.get(name) or TICK_VND.get(root) or _infer_tick_vnd(price_val, small)
    return TICK_USD.get(name) or TICK_USD.get(root) or 0.0

def _decimals_from_tick(tick: float) -> int:
    s = f"{tick:.10f}".rstrip("0").rstrip(".")
    return len(s.split(".")[1]) if "." in s else 0

def round_down_to_tick(value: float, tick: float) -> float:
    if not tick or tick <= 0:
        return float(value or 0.0)
    v, tk = Decimal(str(value)), Decimal(str(tick))
    k = (v / tk).to_integral_value(rounding=ROUND_DOWN)
    return float(k * tk)

# ---------------- public API ----------------
def display_price(symbol: str, last_usd: float, vnd_rate: float, unit: str = "VND") -> tuple[str, str]:
    """
    Tính tên hiển thị & giá hiển thị theo ONUS (auto‑denom + tick-size + format).
    - symbol: 'PEPE_USDT', 'BTC_USDT', ...
    - last_usd: giá USD gốc từ sàn (chưa auto‑denom)
    - vnd_rate: tỷ giá USD→VND hiện tại
    - unit: 'VND' | 'USD'
    Trả: (display_name, price_str)
    """
    name, adj_usd, _mul = auto_denom(symbol, last_usd, vnd_rate)
    small = is_small_name(name)

    if unit.upper() == "USD":
        tick = _lookup_tick(name, "USD", adj_usd, small)
        val = round_down_to_tick(adj_usd, tick)
        return name, fmt_usd_onus(val)

    # VND
    val_vnd = adj_usd * (vnd_rate or 0.0)
    tick = _lookup_tick(name, "VND", val_vnd, small)
    val_vnd = round_down_to_tick(val_vnd, tick)
    dec = _decimals_from_tick(tick) if tick else None
    return name, fmt_vnd_onus(val_vnd, small, decimals=dec)
