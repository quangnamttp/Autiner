# autiner_bot/utils/format_utils.py
def format_price(value: float, currency: str = "VND") -> str:
    """
    Định dạng giá theo yêu cầu:
    - Nếu là VND: giữ số nhỏ nhất có ý nghĩa, không làm tròn vô nghĩa
    - Nếu là USD: giữ 2-4 số thập phân nếu giá nhỏ
    """
    if currency == "VND":
        if value < 1:
            return f"{value:.4f} VND"
        elif value < 1000:
            return f"{value:,.2f} VND"
        else:
            return f"{value:,.0f} VND"
    else:
        if value < 1:
            return f"{value:.4f} USD"
        elif value < 100:
            return f"{value:.2f} USD"
        else:
            return f"{value:,.2f} USD"

def format_percentage(value: float) -> str:
    return f"{value:.2f}%"
