def format_price(value: float, currency: str = "VND", vnd_rate: float = None) -> str:
    """
    Định dạng giá:
    - USD: giữ nguyên giá từ sàn, chỉ thêm dấu phân cách hàng nghìn/phần thập phân để dễ đọc
    - VND: nhân với vnd_rate, giữ nguyên số, nếu < 1 thì bỏ số 0 và dấu '.' phía trước
    """
    try:
        if currency == "VND":
            if vnd_rate:
                value = value * vnd_rate

            raw = f"{value:.12f}".rstrip('0').rstrip('.')  # Giữ đủ thập phân nhưng bỏ 0 vô nghĩa

            if value < 1:
                # Bỏ hết số 0 và dấu '.' phía trước
                raw_no_zero = raw.lstrip('0').lstrip('.')
                # Thêm dấu phân cách nếu số dài
                return f"{raw_no_zero} VND"
            else:
                # Thêm dấu phẩy ngăn cách hàng nghìn
                parts = raw.split('.')
                parts[0] = f"{int(parts[0]):,}"
                return '.'.join(parts) + " VND" if len(parts) > 1 else parts[0] + " VND"

        else:  # USD
            # Lấy giá từ sàn và chỉ thêm dấu phân cách
            raw = str(value)
            if '.' in raw:
                parts = raw.split('.')
                parts[0] = f"{int(parts[0]):,}"
                return '.'.join(parts) + " USD"
            else:
                return f"{int(raw):,} USD"

    except Exception:
        return f"{value} {currency}"
