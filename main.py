import asyncio
import os
from bots.telegram_bot import build_app

if __name__ == "__main__":
    # Yêu cầu: đặt biến môi trường trước (TELEGRAM_BOT_TOKEN, ALLOWED_USER_ID, TZ_NAME)
    app = build_app()
    app.run_polling(close_loop=False)
