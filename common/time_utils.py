from datetime import datetime, time, timedelta
import pytz
from config.settings import TZ_NAME

VN_TZ = pytz.timezone(TZ_NAME)

def now_vn() -> datetime:
    return datetime.now(VN_TZ)

def today_slot_dt(hhmm: str) -> datetime:
    h, m = map(int, hhmm.split(":"))
    n = now_vn()
    return VN_TZ.localize(datetime(n.year, n.month, n.day, h, m, 0))

def fmt_vn(dt: datetime) -> str:
    return dt.strftime("%H:%M %d/%m/%Y")

def seconds_until(dt: datetime) -> int:
    delta = (dt - now_vn()).total_seconds()
    return max(0, int(delta))
