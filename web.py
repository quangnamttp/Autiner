# web.py — chạy Telegram bot bằng WEBHOOK (python-telegram-bot v20+)
import os
from bots.telegram_bot.telegram_bot import build_app
from settings import TELEGRAM_BOT_TOKEN

def main():
    port = int(os.getenv("PORT", "10000"))              # Render sẽ set PORT
    base = os.getenv("WEBHOOK_BASE_URL", "").rstrip("/")  # https://<your-service>.onrender.com
    if not TELEGRAM_BOT_TOKEN or not base:
        raise SystemExit("Missing TELEGRAM_BOT_TOKEN or WEBHOOK_BASE_URL")

    webhook_url = f"{base}/{TELEGRAM_BOT_TOKEN}"

    application = build_app()

    # Chạy server aiohttp bên trong PTB + set webhook
    application.run_webhook(
        listen="0.0.0.0",
        port=port,
        url_path=TELEGRAM_BOT_TOKEN,   # endpoint: /<TOKEN>
        webhook_url=webhook_url,       # URL công khai Telegram sẽ gọi
        drop_pending_updates=True,
    )

if __name__ == "__main__":
    main()
