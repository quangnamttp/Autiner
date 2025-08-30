import os
import asyncio
import threading
import logging

from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from autiner_bot.settings import S
from autiner_bot import menu  # chỉ cần menu

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("autiner")

# ========= Flask =========
app = Flask(__name__)

# ========= PTB Application (async) =========
bot_loop = asyncio.new_event_loop()
application = Application.builder().token(S.TELEGRAM_BOT_TOKEN).build()

# Handlers
application.add_handler(CommandHandler("start", menu.start_command))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, menu.text_handler))

# ========= Webhook helpers =========
def _get_webhook_base():
    # Ưu tiên biến ENV của Render; có thể tự set WEBHOOK_BASE nếu cần
    return (
        os.getenv("RENDER_EXTERNAL_URL")
        or os.getenv("WEBHOOK_BASE")
        or "https://autiner-7mgw.onrender.com"  # fallback
    ).rstrip("/")

async def init_bot():
    await application.initialize()
    await application.start()
    webhook_base = _get_webhook_base()
    webhook_url = f"{webhook_base}/webhook/{S.TELEGRAM_BOT_TOKEN}"
    await application.bot.set_webhook(webhook_url, drop_pending_updates=True)
    log.info("[WEBHOOK] set to %s", webhook_url)

# ========= Flask routes =========
@app.route(f"/webhook/{S.TELEGRAM_BOT_TOKEN}", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True, silent=True)
        if not data:
            return "no json", 400
        update = Update.de_json(data, application.bot)
        asyncio.run_coroutine_threadsafe(application.process_update(update), bot_loop)
        return "OK", 200
    except Exception as e:
        log.exception("webhook error: %s", e)
        return "ERR", 500

@app.route("/health", methods=["GET"])
def health():
    return "ok", 200

@app.route("/", methods=["GET"])
def home():
    return "Autiner Bot Running", 200

# ========= Threads =========
def start_bot_loop():
    asyncio.set_event_loop(bot_loop)
    bot_loop.run_until_complete(init_bot())
    bot_loop.run_forever()

if __name__ == "__main__":
    threading.Thread(target=start_bot_loop, daemon=True).start()
    port = int(os.getenv("PORT", "10000"))  # Render sẽ đặt PORT qua ENV
    app.run(host="0.0.0.0", port=port, use_reloader=False)
