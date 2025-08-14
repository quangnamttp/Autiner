import os
from dotenv import load_dotenv
load_dotenv()

# Telegram
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# MEXC API
MEXC_API_KEY = os.getenv("MEXC_API_KEY")
MEXC_SECRET_KEY = os.getenv("MEXC_SECRET_KEY")

# Giờ hoạt động (UTC+7)
START_TIME = "06:15"
END_TIME = "21:45"

# Tỷ lệ mặc định nếu không lấy được từ API
DEFAULT_USD_VND = 24500.0
