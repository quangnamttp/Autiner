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

import asyncio
asyncio.get_event_loop().run_until_complete(application.initialize())
asyncio.get_event_loop().run_until_complete(application.start())
@app.route("/")
def home():
    return "Autiner Bot Running", 200

@app.route(f"/webhook/{S.TELEGRAM_BOT_TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.update_queue.put_nowait(update)
    return "OK", 200

def run_jobs():
    sched = BackgroundScheduler(timezone=S.TZ_NAME)
    sched.add_job(lambda: asyncio.run(scheduler.job_morning_message()), "cron", hour=6, minute=0)
    sched.add_job(lambda: asyncio.run(scheduler.job_trade_signals()), "cron", hour="6-21", minute="15,45")
    sched.add_job(lambda: asyncio.run(scheduler.job_summary()), "cron", hour=22, minute=0)
    sched.start()

if __name__ == "__main__":
    threading.Thread(target=run_jobs).start()
    app.run(host="0.0.0.0", port=10000)
