# -*- coding: utf-8 -*-
"""Tập trung toàn bộ hằng số/cấu hình dùng chung (đọc từ ENV)."""

import os

# ===== TELEGRAM =====
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ALLOWED_USER_ID    = int(os.getenv("ALLOWED_USER_ID", "0"))

# ===== TIME/LOCALE =====
TZ_NAME      = os.getenv("TZ_NAME", "Asia/Ho_Chi_Minh")
DEFAULT_UNIT = os.getenv("DEFAULT_UNIT", "VND").upper()  # 'VND' | 'USD'

# Slot tín hiệu 30' 06:15 → 21:45
SLOT_TIMES = [
    "06:15","06:45","07:15","07:45","08:15","08:45","09:15","09:45",
    "10:15","10:45","11:15","11:45","12:15","12:45","13:15","13:45",
    "14:15","14:45","15:15","15:45","16:15","16:45","17:15","17:45",
    "18:15","18:45","19:15","19:45","20:15","20:45","21:15","21:45",
]

NUM_SCALPING    = int(os.getenv("NUM_SCALPING", "3"))
HEALTH_POLL_SEC = int(os.getenv("HEALTH_POLL_SEC", "300"))

# ===== HTTP / API =====
HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "10"))
HTTP_RETRY   = int(os.getenv("HTTP_RETRY", "3"))

# MEXC public (futures)
MEXC_TICKER_URL  = os.getenv("MEXC_TICKER_URL",  "https://contract.mexc.com/api/v1/contract/ticker")
MEXC_FUNDING_URL = os.getenv("MEXC_FUNDING_URL", "https://contract.mexc.com/api/v1/contract/fundingRate")
MEXC_KLINES_URL  = os.getenv(
    "MEXC_KLINES_URL",
    "https://contract.mexc.com/api/v1/contract/kline?symbol={sym}&interval=Min1&limit=120"
)

# Tỷ giá USD/VND
USDVND_URL = os.getenv("USDVND_URL", "https://api.exchangerate.host/latest?base=USD&symbols=VND")

# ===== MEXC PRIVATE (để lệnh/account sau này) =====
# 👉 Bạn chỉ set trên Render:
# MEXC_API_KEY=mx0vgl8vcbqeQC9MYS
# MEXC_API_SECRET=3974e94436b0453da81fdb0289be0b8c
MEXC_API_KEY    = os.getenv("MEXC_API_KEY", "")
MEXC_API_SECRET = os.getenv("MEXC_API_SECRET", "")

# ===== Signal Engine params =====
FX_CACHE_TTL        = int(os.getenv("FX_CACHE_TTL", "900"))
VOL24H_FLOOR        = float(os.getenv("VOL24H_FLOOR", "1000000"))
BREAK_VOL_MULT      = float(os.getenv("BREAK_VOL_MULT", "1.8"))
FUNDING_ABS_LIM     = float(os.getenv("FUNDING_ABS_LIM", "0.12"))

ATR_ENTRY_K         = float(os.getenv("ATR_ENTRY_K", "0.35"))
ATR_ZONE_K          = float(os.getenv("ATR_ZONE_K", "0.6"))
ATR_TP_K            = float(os.getenv("ATR_TP_K", "0.9"))
ATR_SL_K            = float(os.getenv("ATR_SL_K", "0.8"))
TTL_MINUTES         = int(os.getenv("TTL_MINUTES", "10"))

TRAIL_START_K       = float(os.getenv("TRAIL_START_K", "0.6"))
TRAIL_STEP_K        = float(os.getenv("TRAIL_STEP_K", "0.25"))

DIVERSITY_POOL_TOPN = int(os.getenv("DIVERSITY_POOL_TOPN", "40"))
SAME_PRICE_EPS      = float(os.getenv("SAME_PRICE_EPS", "0.0008"))
REPEAT_BONUS_DELTA  = float(os.getenv("REPEAT_BONUS_DELTA", "0.6"))
