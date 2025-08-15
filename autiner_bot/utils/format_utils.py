def format_price(value: float, currency: str = "VND", vnd_rate: float = None) -> str:
    """
    Định dạng giá:
    - USD: giữ nguyên giá từ sàn, chỉ thêm phẩy khi >= 1
    - VND: nhân với vnd_rate
        + Nếu >= 1: dùng phẩy tách nghìn, chấm cho thập phân
        + Nếu < 1: bỏ '0.' và số 0 dư, giữ thập phân
    """
    try:
        if currency == "VND":
            if vnd_rate:
                value = value * vnd_rate

            if value >= 1:
                if value < 1000:
                    # Dưới 1000 vẫn giữ thập phân rõ ràng
                    return f"{value:,.4f}".replace(",", "X").replace(".", ",").replace("X", ".") + " VND"
                else:
                    # Trên 1000 chỉ hiển thị nguyên + phân cách hàng nghìn
                    return f"{value:,.0f}".replace(",", ".") + " VND"
            else:
                # Giá quá nhỏ: bỏ '0.' và 0 dư thừa ở đầu
                raw = f"{value:.12f}".rstrip('0').rstrip('.')
                raw_no_zero = raw.replace("0.", "").lstrip('0')
                return raw_no_zero + " VND"

        else:  # USD
            if value >= 1:
                return f"{value:,.8f}".rstrip('0').rstrip('.')
            else:
                return f"{value:.8f}".rstrip('0').rstrip('.')

    except Exception:
        return f"{value} {currency}"
