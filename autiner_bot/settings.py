import os
from dataclasses import dataclass

@dataclass
class Settings:
    # Telegram
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_ALLOWED_USER_ID: int = int(os.getenv("TELEGRAM_ALLOWED_USER_ID", "0"))

    # Timezone
    TZ_NAME: str = os.getenv("TZ_NAME", "Asia/Ho_Chi_Minh")

    # OpenRouter (AI)
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_API_URL: str = os.getenv("OPENROUTER_API_URL", "https://openrouter.ai/api/v1/chat/completions")
    OPENROUTER_MODEL: str = os.getenv("OPENROUTER_MODEL", "deepseek-chat-v3-0324:free")
    # 👉 có thể đổi sang "meta-llama/llama-3.1-8b-instruct:free" nếu muốn gọn, nhanh hơn

    # API MEXC
    MEXC_BASE_URL: str = "https://contract.mexc.com"

    # API Binance P2P (USDT/VND)
    BINANCE_P2P_URL: str = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"


S = Settings()
