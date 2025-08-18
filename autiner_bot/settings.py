# autiner_bot/settings.py
import os
from dataclasses import dataclass

@dataclass
class Settings:
    # Telegram bot config
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_ALLOWED_USER_ID: int = int(os.getenv("TELEGRAM_ALLOWED_USER_ID", "0"))

    # Timezone
    TZ_NAME: str = os.getenv("TZ_NAME", "Asia/Ho_Chi_Minh")

    # Nếu sau này bạn cần thêm chức năng trade trực tiếp,
    # mới bật lại API Key/Secret ở đây
    # MEXC_API_KEY: str = os.getenv("MEXC_API_KEY", "")
    # MEXC_API_SECRET: str = os.getenv("MEXC_API_SECRET", "")

S = Settings()
