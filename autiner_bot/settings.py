import os
from dataclasses import dataclass

@dataclass
class Settings:
    # Telegram
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_ALLOWED_USER_ID: int = int(os.getenv("TELEGRAM_ALLOWED_USER_ID", "0"))

    # Timezone
    TZ_NAME: str = os.getenv("TZ_NAME", "Asia/Ho_Chi_Minh")

    # API Binance
    BINANCE_FUTURES_URL: str = "https://fapi.binance.com"
    BINANCE_P2P_URL: str = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"
