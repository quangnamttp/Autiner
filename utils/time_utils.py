# autiner_bot/utils/time_utils.py
from datetime import datetime
import pytz
from autiner_bot.settings import S

def get_vietnam_time():
    tz = pytz.timezone(S.TZ_NAME)
    return datetime.now(tz)

def format_time(dt=None):
    if dt is None:
        dt = get_vietnam_time()
    return dt.strftime("%H:%M:%S %d-%m-%Y")
