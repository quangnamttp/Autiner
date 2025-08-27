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

    # AI phân tích tín hiệu (qua OpenRouter)
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")

    # Model cho AUTO (scheduler)
    OPENROUTER_MODEL_AUTO: str = os.getenv("OPENROUTER_MODEL_AUTO", "meta-llama/llama-4-maverick:free")

    # Model cho MANUAL (người dùng gõ coin)
    OPENROUTER_MODEL_MANUAL: str = os.getenv("OPENROUTER_MODEL_MANUAL", "deepseek-chat-v3-0324:free")

    # API endpoint OpenRouter
    OPENROUTER_API_URL: str = os.getenv(
        "OPENROUTER_API_URL",
        "https://openrouter.ai/api/v1/chat/completions"
    )

S = Settings()
