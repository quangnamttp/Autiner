# -*- coding: utf-8 -*-
import asyncio, traceback
from datetime import datetime, timedelta, time as dt_time
import pytz
from telegram import Update, ReplyKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import Application, ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

from settings import (
    TELEGRAM_BOT_TOKEN, ALLOWED_USER_ID, TZ_NAME,
    SLOT_TIMES, NUM_SCALPING, HEALTH_POLL_SEC,
    DEFAULT_UNIT
)
from .mexc_api import smart_pick_signals, market_snapshot

# ====== state ======
VN_TZ = pytz.timezone(TZ_NAME)
_current_unit = DEFAULT_UNIT if DEFAULT_UNIT in ("VND","USD") else "VND"
_auto_on = True

# ====== helpers ======
def guard(update: Update) -> bool:
    return not (ALLOWED_USER_ID and update.effective_user and update.effective_user.id != ALLOWED_USER_ID)

def vn_now_str() -> str:
    return datetime.now(VN_TZ).strftime("%H:%M %d/%m/%Y")

def next_slot_info(now: datetime) -> tuple[str, int]:
    today = now.date()
    slots = []
    for hhmm in SLOT_TIMES:
        h, m = map(int, hhmm.split(":"))
        slots.append(VN_TZ.localize(datetime.combine(today, dt_time(h, m))))
    future = [s for s in slots if s > now]
    nxt = future[0] if future else VN_TZ.localize(datetime.combine(today + timedelta(days=1), dt_time(*map(int, SLOT_TIMES[0].split(":")))))
    mins = max(0, int((nxt - now).total_seconds() // 60))
    return nxt.strftime("%H:%M"), mins

# ====== keyboard ======
def _status_btn_text() -> str:
    return f"🔎 Trạng thái ({'ON' if _auto_on else 'OFF'})"

def _auto_btn_text() -> str:
    return "🟢 Auto ON" if not _auto_on else "🔴 Auto OFF"

def _kbd() -> ReplyKeyboardMarkup:
    kb = [
        [_status_btn_text(), "🧪 Test"],
        ["📅 Hôm nay", "📅 Ngày mai"],
        ["📅 Cả tuần", "💰 MEXC VND"],
        ["💵 MEXC USD", _auto_btn_text()],
    ]
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

# ====== handlers ======
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not guard(update): return
    await update.effective_chat.send_message("Chọn thao tác bên dưới.", reply_markup=_kbd())

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not guard(update): return
    _, live, _ = market_snapshot(unit="USD", topn=1)
    text = (
        "📡 Trạng thái bot\n"
        f"• Nguồn: MEXC Futures\n"
        f"• Auto tín hiệu: {'ON 🟢' if _auto_on else 'OFF 🔴'}\n"
        f"• Đơn vị hiện tại: {_current_unit}\n"
        f"• Dữ liệu: {'LIVE ✅' if live else 'DOWN ❌'}"
    )
    await update.effective_chat.send_message(text, reply_markup=_kbd())

async def _toggle_auto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global _auto_on
    _auto_on = not _auto_on
    msg = "✅ ĐÃ BẬT gửi tín hiệu tự động (mỗi 30’)." if _auto_on else "⛔ ĐÃ TẮT gửi tín hiệu tự động."
    await update.effective_chat.send_message(msg, reply_markup=_kbd())

async def set_unit_vnd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global _current_unit
    _current_unit = "VND"
    await update.effective_chat.send_message("✅ Đã chuyển đơn vị sang VND.", reply_markup=_kbd())

async def set_unit_usd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global _current_unit
    _current_unit = "USD"
    await update.effective_chat.send_message("✅ Đã chuyển đơn vị sang USD.", reply_markup=_kbd())

async def macro_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_chat.send_message("📅 Lịch vĩ mô hôm nay: (đang rút gọn).", reply_markup=_kbd())

async def macro_tomorrow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_chat.send_message("📅 Lịch vĩ mô ngày mai: (đang rút gọn).", reply_markup=_kbd())

async def macro_week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_chat.send_message("📅 Lịch vĩ mô cả tuần: (đang rút gọn).", reply_markup=_kbd())

# ====== jobs ======
async def pre_countdown(context: ContextTypes.DEFAULT_TYPE):
    if not _auto_on: return
    chat_id = ALLOWED_USER_ID
    try:
        msg = await context.bot.send_message(chat_id, "⏳ Tín hiệu 30’ tiếp theo — còn 60s")
        for sec in range(59, -1, -1):
            await asyncio.sleep(1)
            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id, message_id=msg.message_id,
                    text=f"⏳ Tín hiệu 30’ tiếp theo — còn {sec:02d}s"
                )
            except Exception:
                pass
    except Exception as e:
        print("[COUNTDOWN_ERROR]", e)

async def send_batch_scalping(context: ContextTypes.DEFAULT_TYPE):
    if not _auto_on: 
        return
    chat_id = ALLOWED_USER_ID
    try:
        signals, highlights, live, rate = smart_pick_signals(_current_unit, NUM_SCALPING)

        if (not live) or (not signals):
            now = datetime.now(VN_TZ)
            nxt_hhmm, mins = next_slot_info(now)
            await context.bot.send_message(
                chat_id,
                f"⚠️ Hệ thống đang gặp sự cố nên **slot {now.strftime('%H:%M')}** không có tín hiệu.\n"
                f"↪️ Dự kiến hoạt động lại vào slot **{nxt_hhmm}** (khoảng {mins} phút nữa).",
                reply_markup=_kbd()
            )
            return

        header = f"📌 Tín hiệu {NUM_SCALPING} lệnh (Scalping) — {vn_now_str()}"
        if highlights:
            header += "\n⭐ Tín hiệu nổi bật: " + " | ".join(highlights[:3])
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

    except Exception as e:
        tb = traceback.format_exc()
        print("[SEND_BATCH_ERROR]\n", tb)
        await context.bot.send_message(
            chat_id,
            f"🚨 Lỗi nội bộ khi tạo tín hiệu: {e.__class__.__name__}: {e}\n→ Mình sẽ thử lại ở slot kế tiếp.",
            reply_markup=_kbd()
        )

# Health monitor
async def health_probe(context: ContextTypes.DEFAULT_TYPE):
    chat_id = ALLOWED_USER_ID
    try:
        coins, live, _ = market_snapshot(unit="USD", topn=1)
        if not live or not coins:
            now = datetime.now(VN_TZ)
            nxt_hhmm, mins = next_slot_info(now)
            await context.bot.send_message(
                chat_id,
                f"🚨 Cảnh báo kết nối: nguồn dữ liệu đang DOWN lúc {now.strftime('%H:%M')}.\n"
                f"↪️ Slot kế tiếp: **{nxt_hhmm}** (~{mins}p)."
            )
    except Exception as e:
        print("[HEALTH_PROBE_ERROR]", e)

# ====== build app ======
def build_app() -> Application:
    app: Application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status_cmd))

    # reply-keyboard actions
    app.add_handler(MessageHandler(filters.Regex(r"^(🟢 Auto ON|🔴 Auto OFF)$"), _toggle_auto))
    app.add_handler(MessageHandler(filters.Regex(r"^🔎 Trạng thái"), status_cmd))
    app.add_handler(MessageHandler(filters.Regex(r"^💰 MEXC VND$"), set_unit_vnd))
    app.add_handler(MessageHandler(filters.Regex(r"^💵 MEXC USD$"), set_unit_usd))
    app.add_handler(MessageHandler(filters.Regex(r"^🧪 Test$"), send_batch_scalping))
    app.add_handler(MessageHandler(filters.Regex(r"^📅 Hôm nay$"), macro_today))
    app.add_handler(MessageHandler(filters.Regex(r"^📅 Ngày mai$"), macro_tomorrow))
    app.add_handler(MessageHandler(filters.Regex(r"^📅 Cả tuần$"), macro_week))

    # schedule 30'
    for hhmm in SLOT_TIMES:
        h, m = map(int, hhmm.split(":"))
        # countdown trước 60s
        mm = (m - 1) % 60
        hh = h if m > 0 else (h - 1)
        app.job_queue.run_daily(pre_countdown,       time=dt_time(hh, mm, tzinfo=VN_TZ))
        app.job_queue.run_daily(send_batch_scalping, time=dt_time(h,  m,  tzinfo=VN_TZ))

    # health probe
    app.job_queue.run_repeating(health_probe, interval=HEALTH_POLL_SEC, first=10)
    return app
