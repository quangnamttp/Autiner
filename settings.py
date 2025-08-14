# settings.py
import os
from dataclasses import dataclass

@dataclass
class Settings:
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_ALLOWED_USER_ID: int = int(os.getenv("TELEGRAM_ALLOWED_USER_ID", "0"))
    TZ_NAME: str = os.getenv("TZ_NAME", "Asia/Ho_Chi_Minh")

    MEXC_API_KEY: str = os.getenv("MEXC_API_KEY", "")
    MEXC_API_SECRET: str = os.getenv("MEXC_API_SECRET", "")

    MEXC_TICKER_URL: str = "https://contract.mexc.com/api/v1/contract/ticker"
    MEXC_FUNDING_URL: str = "https://contract.mexc.com/api/v1/contract/funding_rate"
    MEXC_KLINES_URL: str = "https://contract.mexc.com/api/v1/contract/kline/{sym}?interval=Min1&limit=120"
    MEXC_TICKER_VNDC_URL: str = "https://www.mexc.com/open/api/v2/market/ticker?symbol=USDT_VND"

    HTTP_TIMEOUT: float = 10
    HTTP_RETRY: int = 2
    FX_CACHE_TTL: int = 10

    VOL24H_FLOOR: float = 200_000
    BREAK_VOL_MULT: float = 1.3
    FUNDING_ABS_LIM: float = 0.0005
    ATR_ENTRY_K: float = 0.3
    ATR_ZONE_K: float = 0.2
    ATR_TP_K: float = 1.0
    ATR_SL_K: float = 0.8
    TTL_MINUTES: int = 15
    TRAIL_START_K: float = 0.6
    TRAIL_STEP_K: float = 0.5

    SLOT_START: str = "06:15"
    SLOT_END: str = "21:45"
    SLOT_STEP_MIN: int = 30

settings = Settings()
