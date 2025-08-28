import os
from dataclasses import dataclass

@dataclass
class Settings:
    # Telegram bot
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_ALLOWED_USER_ID: int = int(os.getenv("TELEGRAM_ALLOWED_USER_ID", "0"))

    # Timezone
    TZ_NAME: str = os.getenv("TZ_NAME", "Asia/Ho_Chi_Minh")

    # OpenRouter (AI)
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_MODEL: str = os.getenv("OPENROUTER_MODEL", "deepseek-chat-v3-0324:free")
    OPENROUTER_API_URL: str = os.getenv(
        "OPENROUTER_API_URL", "https://openrouter.ai/api/v1/chat/completions"
    )

S = Settings()
