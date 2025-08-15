def format_price(value: float, currency: str = "VND", vnd_rate: float = None) -> str:
    """
    Định dạng giá hiển thị theo USD hoặc VND.
    """
    try:
        if currency == "VND":
            # Nếu tỷ giá không có, dùng mặc định 25.000
            if not vnd_rate or vnd_rate <= 0:
                vnd_rate = 25_000

            value = value * vnd_rate

            if value >= 1:
                if value < 1000:
                    return f"{value:,.4f}".replace(",", "X").replace(".", ",").replace("X", ".") + " VND"
                else:
                    return f"{value:,.0f}".replace(",", ".") + " VND"
            else:
                raw = f"{value:.12f}".rstrip('0').rstrip('.')
                raw_no_zero = raw.replace("0.", "").lstrip("0")
                return raw_no_zero + " VND"

        else:  # USD
            if value >= 1:
                return f"{value:,.8f}".rstrip('0').rstrip('.')
            else:
                return f"{value:.8f}".rstrip('0').rstrip('.')

    except Exception:
        return f"{value} {currency}"
