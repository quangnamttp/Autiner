def format_price(value: float, currency: str = "VND", vnd_rate: float = None) -> str:
    """
    Định dạng giá:
    - USD: giữ nguyên giá từ sàn, thêm dấu tách hàng nghìn nếu cần
    - VND: nhân với vnd_rate, thêm dấu tách hàng nghìn
    - Nếu giá quá nhỏ (<1): bỏ số 0 và dấu '.' ở đầu
    """
    try:
        if currency == "VND":
            if vnd_rate:
                value = value * vnd_rate

            if value < 1:
                # Bỏ 0 và dấu chấm phía trước
                raw = f"{value:.12f}".rstrip('0').rstrip('.')
                raw_no_zero = raw.lstrip('0').lstrip('.')  # Xóa số 0 và dấu '.'
                return f"{raw_no_zero} VND"
            elif value < 1000:
                return f"{value:,.2f} VND"
            else:
                return f"{value:,.0f} VND"

        else:  # USD
            if value < 1:
                raw = f"{value:.12f}".rstrip('0').rstrip('.')
                raw_no_zero = raw.lstrip('0').lstrip('.')  # Xóa số 0 và dấu '.'
                return f"{raw_no_zero} USD"
            elif value < 100:
                return f"{value:,.4f} USD".rstrip('0').rstrip('.')
            else:
                return f"{value:,.2f} USD"

    except Exception:
        return f"{value} {currency}"
