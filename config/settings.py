import os

# Token và ID người dùng được phép
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_USER_ID = int(os.getenv("ALLOWED_USER_ID", "0"))

# Múi giờ
TZ_NAME = os.getenv("TZ_NAME", "Asia/Ho_Chi_Minh")

# URL Render + Webhook
PUBLIC_URL = os.getenv("PUBLIC_URL", "").rstrip("/")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "autiner_secret")
SELF_URL = os.getenv("SELF_URL", "").rstrip("/")

# Khung giờ gửi tín hiệu
SLOT_TIMES = [
    "06:15","06:45","07:15","07:45","08:15","08:45","09:15","09:45",
    "10:15","10:45","11:15","11:45","12:15","12:45","13:15","13:45",
    "14:15","14:45","15:15","15:45","16:15","16:45","17:15","17:45",
    "18:15","18:45","19:15","19:45","20:15","20:45","21:15","21:45",
]

# Số tín hiệu trong mỗi batch
NUM_SCALPING = 3
NUM_SWING = 2
