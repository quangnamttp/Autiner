# autiner_bot/utils/time_utils.py
"""
Tiện ích thời gian cho múi giờ Việt Nam.
"""

from datetime import datetime
import pytz

VN_TZ = pytz.timezone("Asia/Ho_Chi_Minh")

def get_vietnam_time() -> datetime:
    """
    Lấy datetime hiện tại theo múi giờ Việt Nam.
    """
    return datetime.now(VN_TZ)

# (tuỳ chọn) định dạng nhanh
def format_vietnam_time(dt: datetime, fmt: str = "%H:%M %d/%m/%Y") -> str:
    """
    Định dạng datetime theo VN timezone. Nếu dt chưa có tz, coi như VN.
    """
    if dt.tzinfo is None:
        dt = VN_TZ.localize(dt)
    else:
        dt = dt.astimezone(VN_TZ)
    return dt.strftime(fmt)
