import os
from dataclasses import dataclass

@dataclass
class Settings:
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_ALLOWED_USER_ID: int = int(os.getenv("TELEGRAM_ALLOWED_USER_ID", "0"))
    TZ_NAME: str = os.getenv("TZ_NAME", "Asia/Ho_Chi_Minh")

    # MEXC API (nếu bạn không trade trực tiếp thì để trống cũng được)
    MEXC_API_KEY: str = os.getenv("MEXC_API_KEY", "")
    MEXC_API_SECRET: str = os.getenv("MEXC_API_SECRET", "")

    # AI phân tích coin (dùng OpenRouter)
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_API_URL: str = os.getenv("OPENROUTER_API_URL", "https://openrouter.ai/api/v1/chat/completions")
    OPENROUTER_MODEL: str = os.getenv("OPENROUTER_MODEL", "github/copilot-chat:free")

    # Endpoint MEXC
    MEXC_TICKER_URL: str = "https://contract.mexc.com/api/v1/contract/ticker"
    MEXC_FUNDING_URL: str = "https://contract.mexc.com/api/v1/contract/funding_rate"
    MEXC_KLINES_URL: str = "https://contract.mexc.com/api/v1/contract/kline/{sym}?interval=Min1&limit=120"
    MEXC_TICKER_VNDC_URL: str = "https://www.mexc.com/open/api/v2/market/ticker?symbol=USDT_VND"


S = Settings()
