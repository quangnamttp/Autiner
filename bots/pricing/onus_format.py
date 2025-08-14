# autiner/bots/pricing/onus_format.py
from decimal import Decimal, ROUND_DOWN

def _truncate(val: Decimal, digits: int) -> Decimal:
    q = Decimal(10) ** -digits
    return val.quantize(q, rounding=ROUND_DOWN)

def display_price(symbol: str, price_usd: float, usd_vnd: float, unit: str):
    """
    Trả về tuple (symbol, formatted_price) theo chuẩn ONUS
    """
    if unit.upper() == "USD":
        return symbol, f"{price_usd:,.6f}".replace(",", ".")
    
    pv = Decimal(str(price_usd)) * Decimal(str(usd_vnd))
    if pv < Decimal("0.001"):
        denom = 1_000_000
    elif pv < Decimal("1"):
        denom = 1_000
    else:
        denom = 1

    disp = pv * Decimal(denom)
    if denom == 1:
        if pv >= Decimal("100000"):
            s = f"{_truncate(pv, 0):,.0f}₫"
        elif pv >= Decimal("1000"):
            s = f"{_truncate(pv, 2):,.2f}₫"
        else:
            s = f"{_truncate(pv, 4):,.4f}₫"
        return symbol, s.replace(",", ".")
    else:
        s = f"{_truncate(disp, 4):,.4f}".replace(",", ".")
        suffix = " x1k" if denom == 1_000 else " x1M"
        return symbol, s + suffix + "₫"
