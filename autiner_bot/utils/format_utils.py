def format_price(value: float, currency: str = "VND", vnd_rate: float = None) -> str:
    """
    Định dạng giá theo yêu cầu:
    - Nếu là VND: quy đổi từ USD sang VND nếu có vnd_rate
      + Không làm tròn vô nghĩa
      + Có dấu phẩy ngăn cách hàng nghìn
      + Không hiển thị số 0 trước phần thập phân khi giá nhỏ
    - Nếu là USD: giữ nguyên định dạng phù hợp
    """
    if currency == "VND":
        if vnd_rate:
            value = value * vnd_rate
        if value < 1:
            return f"{value:.8f}".rstrip('0').rstrip('.') + " VND"
        else:
            return f"{value:,.0f} VND"
    else:  # USD
        if value < 0.0001:
            return f"{value:.8f}".rstrip('0').rstrip('.') + " USD"
        elif value < 1:
            return f"{value:.6f}".rstrip('0').rstrip('.') + " USD"
        elif value < 100:
            return f"{value:.4f}".rstrip('0').rstrip('.') + " USD"
        else:
            return f"{value:,.2f} USD"


def format_percentage(value: float) -> str:
    return f"{value:.2f}%"
