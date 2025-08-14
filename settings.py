# autiner/settings.py
from __future__ import annotations
import os
from dataclasses import dataclass

@dataclass
class Settings:
    # Telegram
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_ALLOWED_USER_ID: int = int(os.getenv("TELEGRAM_ALLOWED_USER_ID", "0"))

    # Timezone
    TZ_NAME: str = os.getenv("TZ_NAME", "Asia/Ho_Chi_Minh")

    # MEXC API
    MEXC_API_KEY: str = os.getenv("MEXC_API_KEY", "")
    MEXC_API_SECRET: str = os.getenv("MEXC_API_SECRET", "")

    # MEXC endpoints (Futures)
    MEXC_TICKER_URL: str = "https://contract.mexc.com/api/v1/contract/ticker"
    MEXC_FUNDING_URL: str = "https://contract.mexc.com/api/v1/contract/funding_rate"
    MEXC_KLINES_URL: str = "https://contract.mexc.com/api/v1/contract/kline/{sym}?interval=Min1&limit=120"
    MEXC_TICKER_VNDC_URL: str = "https://www.mexc.com/open/api/v2/market/ticker?symbol=USDT_VND"

    # HTTP config
    HTTP_TIMEOUT: float = 10
    HTTP_RETRY: int = 2

    # Cache tỷ giá
    FX_CACHE_TTL: int = 10  # seconds

    # Logic mặc định
    VOL24H_FLOOR: float = 200_000       # USDT
    BREAK_VOL_MULT: float = 1.3
    FUNDING_ABS_LIM: float = 0.0005     # 0.05%
    ATR_ENTRY_K: float = 0.3
    ATR_ZONE_K: float = 0.2
    ATR_TP_K: float = 1.0
    ATR_SL_K: float = 0.8
    TTL_MINUTES: int = 15
    TRAIL_START_K: float = 0.6
    TRAIL_STEP_K: float = 0.5

    # Chọn coin đa dạng
    DIVERSITY_POOL_TOPN: int = 50
    SAME_PRICE_EPS: float = 0.0002
    REPEAT_BONUS_DELTA: float = 0.4

    # Slot giờ hoạt động
    SLOT_START: str = "06:00"
    SLOT_END: str = "22:00"
    SLOT_STEP_MIN: int = 30

settings = Settings()
