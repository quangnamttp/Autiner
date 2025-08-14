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

# ================= HANDLERS =================
application.add_handler(CommandHandler("start", menu.start_command))
application.add_handler(CallbackQueryHandler(menu.button_handler))


# ================= INIT BOT =================
async def init_bot():
    """Khởi tạo bot và set webhook"""
    await application.initialize()
    await application.start()
    webhook_url = f"https://autiner.onrender.com/webhook/{S.TELEGRAM_BOT_TOKEN}"
    await application.bot.set_webhook(webhook_url, drop_pending_updates=True)
    print(f"[WEBHOOK] Đã set webhook: {webhook_url}")


# ================= WEBHOOK ROUTE =================
@app.route(f"/webhook/{S.TELEGRAM_BOT_TOKEN}", methods=["POST"])
def webhook():
    try:
        update = Update.de_json(request.get_json(force=True), application.bot)
        asyncio.run(application.process_update(update))
    except Exception as e:
        print(f"[ERROR] Webhook: {e}")
    return "OK", 200


@app.route("/")
def home():
    return "Autiner Bot Running", 200


# ================= JOBS =================
def run_jobs():
    sched = BackgroundScheduler(timezone=S.TZ_NAME)

    # 06:00 — Chào buổi sáng (thêm buffer 06:01)
    sched.add_job(lambda: asyncio.run(scheduler.job_morning_message()),
                  "cron", hour=6, minute=0)
    sched.add_job(lambda: asyncio.run(scheduler.job_morning_message()),
                  "cron", hour=6, minute=1)

    # Mỗi 30 phút — Báo trước 1 phút và gửi tín hiệu
    for h in range(6, 22):
        for m in [15, 45]:
            notice_minute = (m - 1) if m > 0 else 59
            sched.add_job(lambda: asyncio.run(scheduler.job_trade_signals_notice()),
                          "cron", hour=h, minute=notice_minute)
            sched.add_job(lambda: asyncio.run(scheduler.job_trade_signals()),
                          "cron", hour=h, minute=m)

    # 22:00 — Tổng kết phiên (thêm buffer 22:01)
    sched.add_job(lambda: asyncio.run(scheduler.job_summary()),
                  "cron", hour=22, minute=0)
    sched.add_job(lambda: asyncio.run(scheduler.job_summary()),
                  "cron", hour=22, minute=1)

    sched.start()


# ================= START APP =================
if __name__ == "__main__":
    # Đảm bảo init bot xong mới chạy job
    def start_all():
        asyncio.run(init_bot())
        run_jobs()

    threading.Thread(target=start_all).start()
    app.run(host="0.0.0.0", port=10000)
