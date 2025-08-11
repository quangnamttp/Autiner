import os

# =======================
# Telegram Bot Settings
# =======================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ALLOWED_USER_ID = int(os.getenv("ALLOWED_USER_ID", "0"))

# =======================
# Timezone
# =======================
TZ_NAME = os.getenv("TZ_NAME", "Asia/Ho_Chi_Minh")

# =======================
# Webhook / Hosting
# =======================
PUBLIC_URL = os.getenv("PUBLIC_URL", "").rstrip("/")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "autiner_secret")
SELF_URL = os.getenv("SELF_URL", "").rstrip("/")

# =======================
# Default Display Unit (VND or USD)
# =======================
DEFAULT_UNIT = os.getenv("DEFAULT_UNIT", "VND").upper()

# =======================
# Slot times for signals (every 30 min from 06:15 → 21:45)
# =======================
SLOT_TIMES = [
    "06:15","06:45","07:15","07:45","08:15","08:45","09:15","09:45",
    "10:15","10:45","11:15","11:45","12:15","12:45","13:15","13:45",
    "14:15","14:45","15:15","15:45","16:15","16:45","17:15","17:45",
    "18:15","18:45","19:15","19:45","20:15","20:45","21:15","21:45",
]

# =======================
# Scalping Signal Settings
# =======================
NUM_SCALPING = 5  # số lượng tín hiệu mỗi batch

# =======================
# MEXC Futures API URLs
# =======================
MEXC_TICKER_URL = "https://contract.mexc.com/api/v1/contract/ticker"
MEXC_FUNDING_URL = "https://contract.mexc.com/api/v1/contract/funding_rate/last-rate"

# {sym} sẽ được thay bằng ví dụ: BTC_USDT
MEXC_KLINES_URL = os.getenv(
    "MEXC_KLINES_URL",
    "https://contract.mexc.com/api/v1/contract/kline?symbol={sym}&interval=Min1&limit=120"
)

HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "10"))
HTTP_RETRY = int(os.getenv("HTTP_RETRY", "2"))

# =======================
# USD→VND Exchange Rate API
# =======================
USDVND_URL = "https://api.exchangerate.host/latest?base=USD&symbols=VND"
FX_CACHE_TTL = int(os.getenv("FX_CACHE_TTL", "1800"))  # 30 phút

# =======================
# Alert thresholds (for highlights)
# =======================
ALERT_FUNDING_ABS = float(os.getenv("ALERT_FUNDING_ABS", "0.05"))  # 5% (0.05)
ALERT_VOLUME_SPIKE = float(os.getenv("ALERT_VOLUME_SPIKE", "2.0")) # x2

# =======================
# Monitor & Health check
# =======================
FAIL_ALERT_COOLDOWN_SEC = int(os.getenv("FAIL_ALERT_COOLDOWN_SEC", "300"))  # 5 phút
HEALTH_POLL_SEC = int(os.getenv("HEALTH_POLL_SEC", "60"))

# =======================
# Signal Filtering & Smart Logic Parameters
# =======================
VOL24H_FLOOR      = int(os.getenv("VOL24H_FLOOR",      "200000"))  # USDT, lọc coin kém thanh khoản
BREAK_VOL_MULT    = float(os.getenv("BREAK_VOL_MULT",  "1.3"))     # Volume_now >= 1.3 x MA20Vol → MARKET
FUNDING_ABS_LIM   = float(os.getenv("FUNDING_ABS_LIM", "0.05"))    # |funding| < 0.05% → MARKET

# =======================
# ATR-based Parameters
# =======================
ATR_ENTRY_K = float(os.getenv("ATR_ENTRY_K", "0.3"))   # khoảng lùi Entry so với giá hiện tại
ATR_ZONE_K  = float(os.getenv("ATR_ZONE_K",  "0.2"))   # bề rộng vùng LIMIT
ATR_TP_K    = float(os.getenv("ATR_TP_K",    "1.0"))   # TP = ±1.0 ATR
ATR_SL_K    = float(os.getenv("ATR_SL_K",    "0.8"))   # SL = ±0.8 ATR

# =======================
# Limit Order Time-to-Live (minutes)
# =======================
TTL_MINUTES = int(os.getenv("TTL_MINUTES", "15"))

# =======================
# Trailing Stop Settings
# =======================
TRAIL_START_K = float(os.getenv("TRAIL_START_K", "0.6"))  # bắt đầu trailing khi lãi ≥ 0.6 ATR
TRAIL_STEP_K  = float(os.getenv("TRAIL_STEP_K",  "0.5"))  # bước dời SL theo 0.5 ATR

# =======================
# Coin Selection Diversity
# =======================
DIVERSITY_POOL_TOPN = int(os.getenv("DIVERSITY_POOL_TOPN", "40"))  # pool top thanh khoản
SAME_PRICE_EPS      = float(os.getenv("SAME_PRICE_EPS",    "0.0005")) # đứng im nếu thay đổi <0.05%
REPEAT_BONUS_DELTA  = float(os.getenv("REPEAT_BONUS_DELTA","0.40"))   # coin lặp lại phải vượt median+0.40
