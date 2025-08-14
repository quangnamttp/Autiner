def format_price(value: float, currency: str = "VND", vnd_rate: float = None) -> str:
    """
    Định dạng giá theo yêu cầu:
    - Nếu là VND: giữ số nhỏ nhất có ý nghĩa, không làm tròn, thêm dấu phẩy ngăn cách hàng nghìn
    - Nếu là USD: giữ nguyên định dạng giống sàn
    - Nếu currency_mode là VND thì value sẽ được nhân với vnd_rate trước khi format
    """
    try:
        if currency == "VND" and vnd_rate:
            value = value * vnd_rate
            # Không làm tròn, giữ số thập phân cần thiết
            if value < 1:
                return f"{value:,.8f} VND".rstrip('0').rstrip('.')
            else:
                return f"{value:,.8f} VND".rstrip('0').rstrip('.')
        else:
            # USD hiển thị y như sàn, không tự động làm tròn vô nghĩa
            if value < 1:
                return f"{value:.8f} USD".rstrip('0').rstrip('.')
            elif value < 100:
                return f"{value:.4f} USD".rstrip('0').rstrip('.')
            else:
                return f"{value:,.2f} USD"
    except Exception:
        return f"{value} {currency}"
