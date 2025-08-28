import os
from dataclasses import dataclass

@dataclass
class Settings:
    # Telegram bot config
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_ALLOWED_USER_ID: int = int(os.getenv("TELEGRAM_ALLOWED_USER_ID", "0"))

    # Timezone
    TZ_NAME: str = os.getenv("TZ_NAME", "Asia/Ho_Chi_Minh")

    # AI config (chỉ dùng 1 model duy nhất)
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")

    # Model AI duy nhất cho cả auto & thủ công
    OPENROUTER_MODEL: str = os.getenv(
        "OPENROUTER_MODEL",
        "meta-llama/llama-3.1-8b-instruct:free"  # ✅ free, JSON tốt hơn
    )

    # API endpoint
    OPENROUTER_API_URL: str = os.getenv(
        "OPENROUTER_API_URL",
        "https://openrouter.ai/api/v1/chat/completions"
    )

S = Settings()
