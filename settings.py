import os

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_USER_ID = int(os.getenv("ALLOWED_USER_ID", "0"))
TZ_NAME = os.getenv("TZ_NAME", "Asia/Ho_Chi_Minh")

PUBLIC_URL = os.getenv("PUBLIC_URL", "").rstrip("/")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "autiner_secret")
SELF_URL = os.getenv("SELF_URL", "").rstrip("/")

SLOT_TIMES = [
    "06:15","06:45","07:15","07:45","08:15","08:45","09:15","09:45",
    "10:15","10:45","11:15","11:45","12:15","12:45","13:15","13:45",
    "14:15","14:45","15:15","15:45","16:15","16:45","17:15","17:45",
    "18:15","18:45","19:15","19:45","20:15","20:45","21:15","21:45",
]
NUM_SCALPING = 3
NUM_SWING = 2

# --- Onus fetch options ---
ONUS_TIMEOUT = float(os.getenv("ONUS_TIMEOUT", "8"))         # giây
ONUS_RETRY = int(os.getenv("ONUS_RETRY", "2"))               # số lần thử mỗi endpoint
ONUS_CACHE_TTL = int(os.getenv("ONUS_CACHE_TTL", "60"))      # cache giây
ONUS_MIN_REFRESH_SEC = int(os.getenv("ONUS_MIN_REFRESH_SEC", "30"))
ONUS_PROXY = os.getenv("ONUS_PROXY", "")  # ví dụ: http://user:pass@host:port (để trống nếu không dùng)
