import asyncio
import time
import pytz
from datetime import datetime, time as dt_time, timedelta
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, ApplicationBuilder, CommandHandler, ContextTypes

from settings import (
    TELEGRAM_BOT_TOKEN, ALLOWED_USER_ID, TZ_NAME, DEFAULT_UNIT,
    SLOT_TIMES, NUM_SCALPING,
    FAIL_ALERT_COOLDOWN_SEC, HEALTH_POLL_SEC
)
from .mexc_api import top_symbols, pick_scalping_signals

VN_TZ = pytz.timezone(TZ_NAME)
_current_unit = DEFAULT_UNIT

_last_fail_alert_ts = 0.0
_is_down = False

def guard(update: Update) -> bool:
    return not (ALLOWED_USER_ID and update.effective_user and update.effective_user.id != ALLOWED_USER_ID)

def vn_now_str():
    now = datetime.now(VN_TZ)
    return now.strftime("%H:%M %d/%m/%Y")

def weekday_vi(dt: datetime) -> str:
    names = ["Thứ Hai","Thứ Ba","Thứ Tư","Thứ Năm","Thứ Sáu","Thứ Bảy","Chủ Nhật"]
    return names[dt.weekday()]

def next_slot_info(now: datetime) -> tuple[str, int]:
    today = now.date()
    slots = []
    for hhmm in SLOT_TIMES:
        h, m = map(int, hhmm.split(":"))
        slots.append(VN_TZ.localize(datetime.combine(today, dt_time(h, m))))
    future = [s for s in slots if s > now]
    if future:
        nxt = future[0]
    else:
        h, m = map(int, SLOT_TIMES[0].split(":"))
        nxt = VN_TZ.localize(datetime.combine(today + timedelta(days=1), dt_time(h, m)))
    mins = max(0, int((nxt - now).total_seconds() // 60))
    return nxt.strftime("%H:%M"), mins

def _fmt_top_line(c: dict, unit: str) -> str:
    sym = c["symbol"].replace("_USDT", "")
    if unit == "VND":
        price = f"{int(round(c['lastPriceVND'])):,}₫".replace(",", ".")
    else:
        price = f"{c['lastPrice']:.4f} USDT".rstrip("0").rstrip(".")
    chg = float(c.get("change24h_pct", 0.0))
    arrow = "🟢" if chg > 0 else ("🔴" if chg < 0 else "⚪")
    chg_s = f"{arrow} {chg:+.2f}%"
    return f"<code>[ {sym} ]</code>  <b>{price}</b>   Δ24h = {chg_s}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not guard(update): return
    await update.effective_chat.send_message(
        "AUTINER đã sẵn sàng.\n"
        "• /top — Top 30 theo đơn vị hiện tại\n"
        "• /status — Kiểm tra trạng thái dữ liệu",
        parse_mode=ParseMode.MARKDOWN
    )

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not guard(update): return
    _, live, _ = top_symbols(unit="USD", topn=1)
    text = (
        "📡 Trạng thái dữ liệu\n"
        "• Nguồn: MEXC Futures\n"
        f"• Trạng thái: {'LIVE ✅' if live else 'DOWN ❌'}\n"
    )
    await update.effective_chat.send_message(text)

async def top_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not guard(update): return
    coins, live, rate = top_symbols(unit=_current_unit, topn=30)
    if not coins:
        await update.effective_chat.send_message("⚠️ Hiện không có dữ liệu. Thử lại sau nhé.")
        return

    head = f"📊 Top 30 Futures (MEXC) — Đơn vị: {_current_unit}"
    lines = [head, ""]
    for c in coins:
        lines.append(_fmt_top_line(c, _current_unit))

    await update.effective_chat.send_message(
        "\n".join(lines),
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True
    )

async def send_batch_scalping(context: ContextTypes.DEFAULT_TYPE):
    chat_id = ALLOWED_USER_ID
    signals, highlights, live, rate = pick_scalping_signals(_current_unit, NUM_SCALPING)

    if (not live) or (not signals):
        now = datetime.now(VN_TZ)
        nxt_hhmm, mins = next_slot_info(now)
        await context.bot.send_message(
            chat_id,
            f"⚠️ Slot {now.strftime('%H:%M')} không có tín hiệu.\n"
            f"↪️ Dự kiến slot tiếp theo: **{nxt_hhmm}** ({mins} phút nữa)."
        )
        return

    header = f"📌 Tín hiệu {NUM_SCALPING} lệnh (Scalping) — {vn_now_str()}"
    if highlights:
        header += "\n⭐ Nổi bật: " + " | ".join(highlights[:3])
    await context.bot.send_message(chat_id, header)

    for s in signals:
        msg = (
            f"📈 {s['token']} ({s['unit']}) — {'🟩' if s['side']=='LONG' else '🟥'} {s['side']}\n\n"
            f"🟢 Loại lệnh: {s['type']}\n"
            f"🔹 Kiểu vào lệnh: {s['orderType']}\n"
            f"💰 Entry: {s['entry']}\n"
            f"🎯 TP: {s['tp']}\n"
            f"🛡️ SL: {s['sl']}\n"
            f"📊 Độ mạnh: {s['strength']}%\n"
            f"📌 Lý do: {s['reason']}\n"
            f"🕒 Thời gian: {vn_now_str()}"
        )
        await context.bot.send_message(chat_id, msg)

def build_app() -> Application:
    app: Application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("top", top_cmd))

    j = app.job_queue
    for hhmm in SLOT_TIMES:
        h, m = map(int, hhmm.split(":"))
        j.run_daily(send_batch_scalping, time=dt_time(h, m, tzinfo=VN_TZ))

    return app
