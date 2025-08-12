# -*- coding: utf-8 -*-
from __future__ import annotations
from decimal import Decimal, ROUND_DOWN, getcontext
getcontext().prec = 28

SMALL_DENOM_SUFFIXES = ("1M", "1000")

# ép hậu tố cho coin siêu nhỏ để nhất quán
FORCE_DENOM = {"PEPE": "1000", "SHIB": "1000", "BONK": "1000", "FLOKI": "1000"}

def _rd(x: float, n: int) -> Decimal:
    q = Decimal("1." + "0"*n) if n>0 else Decimal("1")
    return Decimal(str(x)).quantize(q, rounding=ROUND_DOWN)

def _dot(s: str) -> str:
    return s.replace(",", ".")

def is_small_name(name: str) -> bool:
    return any(str(name).endswith(s) for s in SMALL_DENOM_SUFFIXES)

def auto_denom(symbol: str, last_usd: float, vnd_rate: float) -> tuple[str, float, float]:
    root = str(symbol).replace("_USDT", "")
    # ép hậu tố nếu nằm trong FORCE_DENOM
    if root in FORCE_DENOM:
        tag = FORCE_DENOM[root]
        mul = 1_000_000.0 if tag == "1M" else 1_000.0
        return f"{root}{tag}", (last_usd or 0.0) * mul, mul

    base_vnd = (last_usd or 0.0) * (vnd_rate or 0.0)
    if base_vnd < 0.001:
        return f"{root}1M",  (last_usd or 0.0) * 1_000_000.0, 1_000_000.0
    if base_vnd < 1.0:
        return f"{root}1000", (last_usd or 0.0) * 1_000.0, 1_000.0
    return root, float(last_usd or 0.0), 1.0

def fmt_usd_onus(val_usd: float) -> str:
    x = float(val_usd or 0.0)
    if x >= 1_000:  return _dot(f"{int(x):,}")
    if x >= 1:      return _dot(f"{_rd(x,2):,.2f}")
    return f"{_rd(x,7):f}".rstrip("0").rstrip(".")

def fmt_vnd_onus(val_vnd: float, small: bool) -> str:
    x = float(val_vnd or 0.0)
    if small:         return _dot(f"{_rd(x,4):,.4f}")
    if x >= 100_000:  return _dot(f"{int(x):,}")
    if x >= 1_000:    return _dot(f"{_rd(x,2):,.2f}")
    return _dot(f"{_rd(x,4):,.4f}")

# -------- tick size ----------
TICK_VND = {
    "PEPE1000": 0.0001, "SHIB1000": 0.01, "BONK1000": 0.01,
    "ARC": 0.01, "TRUMP": 1, "BTC": 1, "ETH": 0.01,
}
TICK_USD = {"BTC": 1, "ETH": 0.01}

def _infer_tick_vnd(x: float, small: bool) -> float:
    # fallback khi không có trong TICK_VND
    if small:              return 0.0001 if x < 10 else 0.01
    if x >= 100_000:       return 1
    if x >= 1_000:         return 0.01
    return 0.0001

def _lookup_tick(name: str, unit: str, price_val: float, small: bool) -> float:
    root = name.replace("1M","").replace("1000","")
    if unit.upper() == "VND":
        return TICK_VND.get(name) or TICK_VND.get(root) or _infer_tick_vnd(price_val, small)
    return TICK_USD.get(name) or TICK_USD.get(root) or 0.0  # USD thường không cần

def round_down_to_tick(value: float, tick: float) -> float:
    if not tick or tick <= 0: return float(value or 0.0)
    v, tk = Decimal(str(value)), Decimal(str(tick))
    k = (v / tk).to_integral_value(rounding=ROUND_DOWN)
    return float(k * tk)

# -------- public ----------
def display_price(symbol: str, last_usd: float, vnd_rate: float, unit: str="VND") -> tuple[str, str]:
    name, adj_usd, _ = auto_denom(symbol, last_usd, vnd_rate)
    small = is_small_name(name)

    if unit.upper() == "USD":
        tick = _lookup_tick(name, "USD", adj_usd, small)
        val  = round_down_to_tick(adj_usd, tick)
        return name, fmt_usd_onus(val)

    val_vnd = adj_usd * (vnd_rate or 0.0)
    tick = _lookup_tick(name, "VND", val_vnd, small)
    val_vnd = round_down_to_tick(val_vnd, tick)
    return name, fmt_vnd_onus(val_vnd, small)
