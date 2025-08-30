import os
from dataclasses import dataclass

@dataclass
class Settings:
    # Telegram
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_ALLOWED_USER_ID: int = int(os.getenv("TELEGRAM_ALLOWED_USER_ID", "0"))
    TZ_NAME: str = os.getenv("TZ_NAME", "Asia/Ho_Chi_Minh")

    # Binance API
    BINANCE_API_KEY: str = os.getenv("BINANCE_API_KEY", "")
    BINANCE_API_SECRET: str = os.getenv("BINANCE_API_SECRET", "")

    # Binance Futures REST API
    BINANCE_BASE_URL: str = "https://fapi.binance.com"
    BINANCE_TICKER_URL: str = BINANCE_BASE_URL + "/fapi/v1/ticker/price"         # Giá hiện tại
    BINANCE_FUNDING_URL: str = BINANCE_BASE_URL + "/fapi/v1/fundingRate"        # Funding rate
    BINANCE_KLINES_URL: str = BINANCE_BASE_URL + "/fapi/v1/klines"              # Nến (ohlcv)
    BINANCE_TICKER_24H_URL: str = BINANCE_BASE_URL + "/fapi/v1/ticker/24hr"     # Volume, biến động 24h

# Instance để main.py gọi
S = Settings()
