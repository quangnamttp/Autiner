# autiner_bot/main.py
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler
from autiner_bot.settings import S
from autiner_bot import menu, scheduler
import asyncio
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)

# Tạo bot Application
application = Application.builder().token(S.TELEGRAM_BOT_TOKEN).build()

# Thêm handlers
application.add_handler(CommandHandler("start", menu.start_command))
application.add_handler(CallbackQueryHandler(menu.button_handler))

# Event loop chung
loop = asyncio.get_event_loop()

# ---- Khởi tạo bot & webhook ----
async def init_bot():
    await application.initialize()
    await application.start()
    webhook_url = f"https://autiner.onrender.com/webhook/{S.TELEGRAM_BOT_TOKEN}"
    await application.bot.set_webhook(webhook_url, drop_pending_updates=True)
    print(f"[WEBHOOK] Đã set: {webhook_url}")

# ---- Webhook endpoint ----
@app.route(f"/webhook/{S.TELEGRAM_BOT_TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    loop.create_task(application.process_update(update))
    return "OK", 200

@app.route("/")
def home():
    return "Autiner Bot Running", 200

# ---- Scheduler ----
def run_jobs():
    sched = BackgroundScheduler(timezone=S.TZ_NAME)

    # 06:00 sáng
    sched.add_job(lambda: loop.create_task(scheduler.job_morning_message()), "cron", hour=6, minute=0)

    # Mỗi 30 phút
    for h in range(6, 22):
        for m in [15, 45]:
            # Báo trước
            sched.add_job(lambda: loop.create_task(scheduler.job_trade_signals_notice()),
                          "cron", hour=h, minute=(m - 1 if m > 0 else 59))
            # Gửi tín hiệu
            sched.add_job(lambda: loop.create_task(scheduler.job_trade_signals()),
                          "cron", hour=h, minute=m)

    # 22:00 tối
    sched.add_job(lambda: loop.create_task(scheduler.job_summary()), "cron", hour=22, minute=0)

    sched.start()
    print("[JOB] Scheduler started")

if __name__ == "__main__":
    loop.create_task(init_bot())
    run_jobs()
    app.run(host="0.0.0.0", port=10000)
