def format_price(value: float, currency: str = "VND", vnd_rate: float = None) -> str:
    """
    Định dạng giá:
    - Nếu là VND: nhân với vnd_rate, hiển thị kèm 'VND'
    - Nếu là USD: giữ nguyên giá trị gốc từ sàn, hiển thị kèm 'USD'
    - Không làm tròn vô nghĩa, giữ số thập phân cần thiết
    """
    try:
        if currency == "VND":
            if vnd_rate:
                value = value * vnd_rate
            # VND: hiển thị dấu phẩy ngăn cách hàng nghìn
            if value < 1:
                return f"{value:,.8f} VND".rstrip('0').rstrip('.')
            elif value < 1000:
                return f"{value:,.2f} VND"
            else:
                return f"{value:,.0f} VND"
        else:
            # USD: giữ định dạng giống sàn
            if value < 1:
                return f"{value:.8f} USD".rstrip('0').rstrip('.')
            elif value < 100:
                return f"{value:.4f} USD".rstrip('0').rstrip('.')
            else:
                return f"{value:,.2f} USD"
    except Exception:
        return f"{value} {currency}"
