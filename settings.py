from __future__ import annotations
import os
from dataclasses import dataclass

@dataclass
class Settings:
    # Telegram
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_ALLOWED_USER_ID: int = int(os.getenv("TELEGRAM_ALLOWED_USER_ID", "0"))

    # Timezone
    TZ_NAME: str = "Asia/Ho_Chi_Minh"

    # MEXC API
    MEXC_API_KEY: str = os.getenv("MEXC_API_KEY", "")
    MEXC_API_SECRET: str = os.getenv("MEXC_API_SECRET", "")

    # MEXC endpoints
    MEXC_TICKER_URL: str = "https://contract.mexc.com/api/v1/contract/ticker"
    MEXC_TICKER_VNDC_URL: str = "https://www.mexc.com/open/api/v2/market/ticker?symbol=USDT_VND"

    # HTTP
    HTTP_TIMEOUT: float = 10
    HTTP_RETRY: int = 2

    # Slot times
    SLOT_START: str = "06:15"
    SLOT_END: str = "21:45"
    SLOT_STEP_MIN: int = 30

settings = Settings()
