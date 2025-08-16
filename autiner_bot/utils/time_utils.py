from datetime import datetime
import pytz
from autiner_bot.settings import S

# Timezone VN lấy từ settings
VN_TZ = pytz.timezone(S.TZ_NAME)

def get_vietnam_time() -> datetime:
    """Lấy thời gian hiện tại theo múi giờ VN"""
    return datetime.now(VN_TZ)

def format_time(dt: datetime | None = None, fmt: str = "%H:%M:%S %d-%m-%Y") -> str:
    """
    Format thời gian theo định dạng tùy chọn.
    - Default: 'HH:MM:SS dd-mm-YYYY'
    """
    if dt is None:
        dt = get_vietnam_time()
    return dt.strftime(fmt)

def utc_to_vietnam(utc_dt: datetime) -> datetime:
    """Chuyển từ UTC datetime sang VN datetime"""
    if utc_dt.tzinfo is None:
        utc_dt = pytz.utc.localize(utc_dt)
    return utc_dt.astimezone(VN_TZ)
