def format_price(value: float, currency: str = "VND", rate: float = None) -> str:
    """
    Định dạng giá:
    - Nếu VND: nhân với rate, bỏ số 0 trước dấu thập phân, không làm tròn, thêm dấu phẩy
    - Nếu USD: giữ nguyên giá trị từ sàn (2-4 số thập phân nếu nhỏ)
    """
    if currency.upper() == "VND":
        if rate is None:
            raise ValueError("Cần truyền tỷ giá USD/VND khi hiển thị giá VND")

        vnd_value = value * rate
        if vnd_value < 1:
            # Bỏ số 0 trước dấu chấm, giữ nguyên độ dài cần thiết
            return f"{vnd_value:.10f}".rstrip("0").rstrip(".").replace("0.", ".") + " VND"
        else:
            # Thêm dấu phẩy phân tách nghìn, không làm tròn
            return f"{vnd_value:,.10f}".rstrip("0").rstrip(".") + " VND"

    else:  # USD
        if value < 1:
            return f"{value:.4f} USD"
        elif value < 100:
            return f"{value:.2f} USD"
        else:
            return f"{value:,.2f} USD"


def format_percentage(value: float) -> str:
    return f"{value:.2f}%"
