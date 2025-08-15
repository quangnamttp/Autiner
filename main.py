from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from apscheduler.schedulers.background import BackgroundScheduler
import asyncio
import threading

from autiner_bot.settings import S
from autiner_bot import menu, scheduler

# Flask app
app = Flask(__name__)

# ====== Bot Application ======
bot_loop = asyncio.new_event_loop()
application = Application.builder().token(S.TELEGRAM_BOT_TOKEN).build()

# ====== Handlers ======
application.add_handler(CommandHandler("start", menu.start_command))
# Xử lý các nút trong Reply Keyboard
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, menu.text_handler))

# ====== Init bot & webhook ======
async def init_bot():
    await application.initialize()
    await application.start()
    webhook_url = f"https://autiner.onrender.com/webhook/{S.TELEGRAM_BOT_TOKEN}"
    await application.bot.set_webhook(webhook_url, drop_pending_updates=True)
    print(f"[WEBHOOK] Đã set: {webhook_url}")

# ====== Webhook Endpoint ======
@app.route(f"/webhook/{S.TELEGRAM_BOT_TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    asyncio.run_coroutine_threadsafe(application.process_update(update), bot_loop)
    return "OK", 200

@app.route("/")
def home():
    return "Autiner Bot Running", 200

# ====== Scheduler ======
def run_jobs():
    sched = BackgroundScheduler(timezone=S.TZ_NAME)

    # 06:00 — Chào buổi sáng
    sched.add_job(lambda: asyncio.run_coroutine_threadsafe(
        scheduler.job_morning_message(), bot_loop
    ), "cron", hour=6, minute=0)

    # Mỗi 30 phút
    for h in range(6, 22):
        for m in [15, 45]:
            # Báo trước
            sched.add_job(lambda: asyncio.run_coroutine_threadsafe(
                scheduler.job_trade_signals_notice(), bot_loop
            ), "cron", hour=h, minute=(m - 1 if m > 0 else 59))
            # Gửi tín hiệu
            sched.add_job(lambda: asyncio.run_coroutine_threadsafe(
                scheduler.job_trade_signals(), bot_loop
            ), "cron", hour=h, minute=m)

    # 22:00 — Tổng kết
    sched.add_job(lambda: asyncio.run_coroutine_threadsafe(
        scheduler.job_summary(), bot_loop
    ), "cron", hour=22, minute=0)

    sched.start()
    print("[JOB] Scheduler started")

# ====== Start Threads ======
def start_bot_loop():
    asyncio.set_event_loop(bot_loop)
    bot_loop.run_until_complete(init_bot())
    bot_loop.run_forever()

if __name__ == "__main__":
    threading.Thread(target=start_bot_loop, daemon=True).start()
    threading.Thread(target=run_jobs, daemon=True).start()
    app.run(host="0.0.0.0", port=10000)
