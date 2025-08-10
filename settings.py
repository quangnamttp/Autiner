import os

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ALLOWED_USER_ID = int(os.getenv("ALLOWED_USER_ID", "0"))

# Timezone
TZ_NAME = os.getenv("TZ_NAME", "Asia/Ho_Chi_Minh")

# Webhook / Hosting
PUBLIC_URL = os.getenv("PUBLIC_URL", "").rstrip("/")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "autiner_secret")
SELF_URL = os.getenv("SELF_URL", "").rstrip("/")

# Đơn vị hiển thị mặc định: VND hoặc USD
DEFAULT_UNIT = os.getenv("DEFAULT_UNIT", "VND").upper()

# Slot 30' từ 06:15 → 21:45
SLOT_TIMES = [
    "06:15","06:45","07:15","07:45","08:15","08:45","09:15","09:45",
    "10:15","10:45","11:15","11:45","12:15","12:45","13:15","13:45",
    "14:15","14:45","15:15","15:45","16:15","16:45","17:15","17:45",
    "18:15","18:45","19:15","19:45","20:15","20:45","21:15","21:45",
]
# Scalping-only
NUM_SCALPING = 5
NUM_SWING = 0

# MEXC Futures API
MEXC_TICKER_URL = "https://contract.mexc.com/api/v1/contract/ticker"
MEXC_FUNDING_URL = "https://contract.mexc.com/api/v1/contract/funding_rate/last-rate"
HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "10"))
HTTP_RETRY = int(os.getenv("HTTP_RETRY", "2"))

# Tỷ giá USD→VND
USDVND_URL = "https://api.exchangerate.host/latest?base=USD&symbols=VND"
FX_CACHE_TTL = int(os.getenv("FX_CACHE_TTL", "1800"))  # 30 phút

# Ngưỡng “tín hiệu khẩn” (đang dùng cho highlight trong batch)
ALERT_FUNDING_ABS = float(os.getenv("ALERT_FUNDING_ABS", "0.05"))  # 5% (0.05)
ALERT_VOLUME_SPIKE = float(os.getenv("ALERT_VOLUME_SPIKE", "2.0")) # x2
