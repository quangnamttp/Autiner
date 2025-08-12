# price_onus.py
# -*- coding: utf-8 -*-
from __future__ import annotations
from decimal import Decimal, ROUND_DOWN, getcontext
import math

getcontext().prec = 28

SMALL_DENOM_SUFFIXES = ("1M", "1000")

# ======================= core ONUS rules =======================
def _rd(x: float, n: int) -> Decimal:
    q = Decimal("1." + "0"*n) if n > 0 else Decimal("1")
    return Decimal(str(x)).quantize(q, rounding=ROUND_DOWN)

def _dot(s: str) -> str:
    return s.replace(",", ".")

def is_small_name(name: str) -> bool:
    return any(str(name).endswith(s) for s in SMALL_DENOM_SUFFIXES)

def auto_denom(symbol: str, last_usd: float, vnd_rate: float) -> tuple[str, float, float]:
    """
    Trả (display_name, adjusted_usd, multiplier)
    - Nếu last_usd * vnd_rate < 0.001  -> hậu tố '1M',  nhân 1_000_000
    - elif < 1                         -> hậu tố '1000', nhân 1_000
    - else giữ nguyên
    """
    root = str(symbol).replace("_USDT", "")
    base_vnd = (last_usd or 0.0) * (vnd_rate or 0.0)
    if base_vnd < 0.001:
        return f"{root}1M",  (last_usd or 0.0) * 1_000_000.0, 1_000_000.0
    if base_vnd < 1.0:
        return f"{root}1000", (last_usd or 0.0) * 1_000.0, 1_000.0
    return root, float(last_usd or 0.0), 1.0

def fmt_usd_onus(val_usd: float) -> str:
    x = float(val_usd or 0.0)
    if x >= 1_000:
        return _dot(f"{int(x):,}")
    if x >= 1:
        return _dot(f"{_rd(x,2):,.2f}")
    return f"{_rd(x,7):f}".rstrip("0").rstrip(".")

def fmt_vnd_onus(val_vnd: float, small: bool) -> str:
    x = float(val_vnd or 0.0)
    if small:
        return _dot(f"{_rd(x,4):,.4f}")   # coin mệnh giá nhỏ: 4 lẻ cố định
    if x >= 100_000:
        return _dot(f"{int(x):,}")       # mệnh giá lớn: 0 lẻ
    if x >= 1_000:
        return _dot(f"{_rd(x,2):,.2f}")  # trung bình: 2 lẻ
    return _dot(f"{_rd(x,4):,.4f}")      # rất nhỏ: 4 lẻ

# ======================= tick-size layer =======================
def round_down_to_tick(value: float, tick: float) -> float:
    """Làm tròn xuống theo bước giá tick (tránh sai khác so với UI sàn)."""
    if not tick or tick <= 0:
        return float(value or 0.0)
    v = Decimal(str(value))
    tk = Decimal(str(tick))
    k = (v / tk).to_integral_value(rounding=ROUND_DOWN)
    return float(k * tk)

# Tick map cho những cặp hay dùng (đơn vị theo **đơn vị hiển thị**)
# Nếu hiển thị VND thì dùng map VND; nếu hiển thị USD thì dùng map USD.
TICK_VND = {
    # mệnh giá nhỏ (…1000/…1M)
    "PEPE1000": 0.0001,
    "SHIB1000": 0.01,
    "BONK1000": 0.01,
    # mệnh giá vừa/lớn
    "ARC": 0.01,
    "TRUMP": 1,
    "BTC": 1,
    "ETH": 0.01,
}

TICK_USD = {
    "BTC": 1,
    "ETH": 0.01,
    # coin siêu nhỏ sau auto-denom vẫn < 1 USD → 7 lẻ là đủ, thường không cần tick,
    # nhưng bạn có thể khai báo nếu muốn.
}

def _lookup_tick(display_name: str, unit: str) -> float:
    root = display_name.replace("1M", "").replace("1000", "")
    if unit.upper() == "VND":
        # ưu tiên tên đã auto-denom (PEPE1000, SHIB1000…), sau đó tới root
        return TICK_VND.get(display_name) or TICK_VND.get(root) or 0.0
    return TICK_USD.get(display_name) or TICK_USD.get(root) or 0.0

# ======================= public API =======================
def display_price(symbol: str, last_usd: float, vnd_rate: float, unit: str = "VND") -> tuple[str, str]:
    """
    Tính tên hiển thị & giá hiển thị (đã áp dụng auto‑denom + tick size).
    Trả: (display_name, price_str)
    """
    name, adj_usd, _mul = auto_denom(symbol, last_usd, vnd_rate)
    small = is_small_name(name)

    if unit.upper() == "USD":
        tick = _lookup_tick(name, "USD")
        price_usd = adj_usd
        price_usd = round_down_to_tick(price_usd, tick) if tick else price_usd
        return name, fmt_usd_onus(price_usd)

    # VND
    tick = _lookup_tick(name, "VND")
    price_vnd = adj_usd * (vnd_rate or 0.0)
    price_vnd = round_down_to_tick(price_vnd, tick) if tick else price_vnd
    return name, fmt_vnd_onus(price_vnd, small)
