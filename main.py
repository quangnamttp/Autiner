# autiner_bot/main.py
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler
from autiner_bot.settings import S
from autiner_bot import menu
import asyncio
import threading
from apscheduler.schedulers.background import BackgroundScheduler
from autiner_bot import scheduler

app = Flask(__name__)
application = Application.builder().token(S.TELEGRAM_BOT_TOKEN).build()

# Handlers
application.add_handler(CommandHandler("start", menu.start_command))
application.add_handler(CallbackQueryHandler(menu.button_handler))

# Khởi tạo bot
asyncio.get_event_loop().run_until_complete(application.initialize())
asyncio.get_event_loop().run_until_complete(application.start())

@app.route("/")
def home():
    return "Autiner Bot Running", 200

@app.route(f"/webhook/{S.TELEGRAM_BOT_TOKEN}", methods=["POST"])
async def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    await application.process_update(update)
    return "OK", 200

def run_jobs():
    sched = BackgroundScheduler(timezone=S.TZ_NAME)

    # 06:00 — Chào buổi sáng
    sched.add_job(lambda: asyncio.run(scheduler.job_morning_message()), "cron", hour=6, minute=0)

    # Mỗi 30 phút — Báo trước 1 phút rồi gửi tín hiệu
    for h in range(6, 22):
        for m in [15, 45]:
            # Báo trước
            sched.add_job(lambda: asyncio.run(scheduler.job_notice_before_signal()),
                          "cron", hour=h, minute=m-1 if m > 0 else 59)
            # Gửi tín hiệu
            sched.add_job(lambda: asyncio.run(scheduler.job_trade_signals()),
                          "cron", hour=h, minute=m)

    # 22:00 — Tổng kết phiên
    sched.add_job(lambda: asyncio.run(scheduler.job_summary()), "cron", hour=22, minute=0)

    sched.start()

if __name__ == "__main__":
    threading.Thread(target=run_jobs).start()
    app.run(host="0.0.0.0", port=10000)
