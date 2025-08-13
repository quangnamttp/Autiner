# bots/telegram_bot/telegram_bot.py
# -*- coding: utf-8 -*-
"""
Autiner Telegram Bot (v2)
- Menu: 🔎 Trạng thái | 🟢/🔴 Auto ON/OFF | 🧪 Test | 💰/💵 đổi đơn vị
- Slot: 06:15 → 21:45 mỗi 30' (thông báo trước 1 phút, KHÔNG đếm ngược)
- Gọi: morning_report (06:00) & night_summary (22:00) nếu có
- Không block event-loop: tác vụ nặng chạy trong thread + timeout
"""

from __future__ import annotations
import asyncio
from datetime import datetime, timedelta, time as dt_time, date
import pytz
from telegram import Update, ReplyKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application, ApplicationBuilder, CommandHandler,
    MessageHandler, ContextTypes, filters
)

# ===== settings =====
from settings import (
    TELEGRAM_BOT_TOKEN, ALLOWED_USER_ID, TZ_NAME,
    SLOT_TIMES, NUM_SCALPING, HEALTH_POLL_SEC,
    DEFAULT_UNIT
)

# ===== domain modules =====
# Morning/Night
try:
    from bots.pricing.morning_report import build_morning_text
except Exception:
    build_morning_text = None

try:
    from bots.pricing.night_summary import build_night_message
except Exception:
    build_night_message = None

# MEXC client để kiểm tra live + keep-alive
from bots.mexc_client import fetch_tickers, health_ping

# ===== Signal Engine =====
_signal_fn = None
try:
    from bots.signals.signal_engine import generate_scalping_signals as _signal_fn
except Exception:
    _signal_fn = None

def _call_signals(unit: str, n: int):
    """
    Chuẩn hoá kết quả trả về từ engine:
    - Nếu engine trả (signals, highlights, live, rate) -> lấy signals
    - Nếu lỡ trả list -> dùng trực tiếp
    """
    if not _signal_fn:
        return []
    out = _signal_fn(unit, n)
    if isinstance(out, tuple):
        return out[0] or []
    return out or []

# ===== globals =====
VN_TZ = pytz.timezone(TZ_NAME)
_current_unit = DEFAULT_UNIT if DEFAULT_UNIT in ("VND", "USD") else "VND"
_auto_on = True


# ===== helpers =====
def guard(update: Update) -> bool:
    return not (ALLOWED_USER_ID and update.effective_user and update.effective_user.id != ALLOWED_USER_ID)

def vn_now() -> datetime:
    return datetime.now(VN_TZ)

def vn_now_str() -> str:
    return vn_now().strftime("%H:%M %d/%m/%Y")

def _localize_today_time(h: int, m: int) -> datetime:
    today = date.today()
    return VN_TZ.localize(datetime.combine(today, dt_time(h, m)))

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

def _time_minus_one_minute(h: int, m: int) -> tuple[int, int]:
    if m == 0:
        return ((h - 1) % 24, 59)
    return (h, m - 1)

# ===== UI =====
BTN_STATUS = "🔎 Trạng thái"
BTN_TEST   = "🧪 Test"

def main_keyboard() -> ReplyKeyboardMarkup:
    auto_lbl = "🟢 Auto ON" if _auto_on else "🔴 Auto OFF"
    unit_lbl = "💰 MEXC VND" if _current_unit == "VND" else "💵 MEXC USD"
    rows = [
        [BTN_STATUS, auto_lbl],
        [BTN_TEST, unit_lbl],
    ]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)

# ===== thread offload =====
async def _to_thread(func, *args, timeout: int = 25, **kwargs):
    async def _run():
        return await asyncio.to_thread(func, *args, **kwargs)
    try:
        return await asyncio.wait_for(_run(), timeout=timeout)
    except Exception:
        return None

# ===== commands =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not guard(update): return
    await update.effective_chat.send_message(
        "AUTINER đã sẵn sàng. Chọn từ menu dưới nhé.",
        reply_markup=main_keyboard()
    )

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not guard(update): return
    tick = await _to_thread(fetch_tickers, timeout=8)
    live = bool(tick)
    await update.effective_chat.send_message(
        f"📡 Dữ liệu MEXC: {'LIVE ✅' if live else 'DOWN ❌'}\n"
        f"• Đơn vị: {_current_unit}\n"
        f"• Auto: {'ON' if _auto_on else 'OFF'}",
        reply_markup=main_keyboard()
    )

async def toggle_auto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not guard(update): return
    global _auto_on
    _auto_on = not _auto_on
    await update.effective_chat.send_message(
        f"⚙️ Auto tín hiệu: {'🟢 ON' if _auto_on else '🔴 OFF'}",
        reply_markup=main_keyboard()
    )

async def toggle_unit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not guard(update): return
    global _current_unit
    _current_unit = "USD" if _current_unit == "VND" else "VND"
    await update.effective_chat.send_message(
        f"💱 Đã chuyển đơn vị sang: **{_current_unit}**",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_keyboard()
    )

async def test_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Test FULL PIPELINE:
    1) Kiểm tra live
    2) Gửi 06:00 (nếu có)
    3) Tạo & gửi batch tín hiệu
    4) Gửi 22:00 (nếu có)
    5) Health ping
    """
    if not guard(update): return
    chat_id = update.effective_chat.id

    # 1) status
    tick = await _to_thread(fetch_tickers, timeout=8)
    live = bool(tick)
    await context.bot.send_message(chat_id, f"📡 MEXC: {'LIVE ✅' if live else 'DOWN ❌'} | Đơn vị: {_current_unit} | Auto: {'ON' if _auto_on else 'OFF'}", reply_markup=main_keyboard())

    # 2) morning sample
    if build_morning_text:
        text6 = await _to_thread(build_morning_text, _current_unit, "Trương", timeout=12)
        if text6:
            await context.bot.send_message(chat_id, text6)

    # 3) signals
    sigs = await _to_thread(_call_signals, _current_unit, NUM_SCALPING, timeout=28)
    if not sigs:
        await context.bot.send_message(chat_id, "⚠️ Engine chưa trả tín hiệu (thiếu dữ liệu hoặc lỗi).", reply_markup=main_keyboard())
    else:
        header = f"📌 (TEST) {len(sigs)} lệnh — {vn_now_str()}"
        await context.bot.send_message(chat_id, header)
        for s in sigs:
            side_icon = '🟩' if s.get('side') == 'LONG' else '🟥'
            msg = (
                f"📈 {s.get('token')} ({s.get('unit')}) — {side_icon} {s.get('side')} | {s.get('orderType','').upper()}\n\n"
                f"💰 Entry: {s.get('entry')}\n"
                f"🎯 TP: {s.get('tp')}    🛡️ SL: {s.get('sl')}\n"
                f"📊 Độ mạnh: {s.get('strength','--')}%  |  Khung: 1–5m\n"
                f"📌 Lý do:\n{s.get('reason','(n/a)')}\n"
                f"🕒 {vn_now_str()}"
            )
            await context.bot.send_message(chat_id, msg, reply_markup=main_keyboard())

    # 4) night sample
    if build_night_message:
        text22 = await _to_thread(build_night_message, "Trương", timeout=8)
        if text22:
            await context.bot.send_message(chat_id, text22, parse_mode=ParseMode.MARKDOWN)

    # 5) health ping
    await _to_thread(health_ping, timeout=5)
    await context.bot.send_message(chat_id, "✅ Test hoàn tất.", reply_markup=main_keyboard())


# ===== PRE-NOTIFY trước slot 1 phút =====
async def pre_notify(context: ContextTypes.DEFAULT_TYPE):
    if not _auto_on:
        return
    chat_id = ALLOWED_USER_ID
    now = vn_now()
    nxt_str, mins = next_slot_info(now)
    # Nếu đúng lịch này là 1 phút trước slot kế tiếp, gửi thông báo
    await context.bot.send_message(
        chat_id,
        f"⏱️ Tín hiệu tiếp theo sẽ diễn ra lúc **{nxt_str}** (khoảng 1 phút nữa). Hãy cân nhắc chuẩn bị vào lệnh.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_keyboard()
    )

# ===== gửi batch tín hiệu đúng hh:mm:00 =====
async def send_batch_scalping(context: ContextTypes.DEFAULT_TYPE):
    if not _auto_on or not _signal_fn:
        return
    chat_id = ALLOWED_USER_ID

    sigs = await _to_thread(_call_signals, _current_unit, NUM_SCALPING, timeout=30)
    if not sigs:
        now = vn_now()
        nxt_hhmm, mins = next_slot_info(now)
        await context.bot.send_message(
            chat_id,
            f"⚠️ Slot {now.strftime('%H:%M')} chưa đủ dữ liệu để tạo tín hiệu.\n"
            f"🗓️ Dự kiến slot kế tiếp **{nxt_hhmm}** (~{mins}’).",
            reply_markup=main_keyboard()
        )
        return

    header = f"📌 Tín hiệu {len(sigs)} lệnh (Scalping) — {vn_now_str()}"
    await context.bot.send_message(chat_id, header)

    for s in sigs:
        side_icon = '🟩' if s.get('side') == 'LONG' else '🟥'
        msg = (
            f"📈 {s.get('token')} ({s.get('unit')}) — {side_icon} {s.get('side')} | {s.get('orderType','').upper()}\n\n"
            f"💰 Entry: {s.get('entry')}\n"
            f"🎯 TP: {s.get('tp')}    🛡️ SL: {s.get('sl')}\n"
            f"📊 Độ mạnh: {s.get('strength','--')}%  |  Khung: 1–5m\n"
            f"📌 Lý do (MA/RSI):\n{s.get('reason','(n/a)')}\n"
            f"🕒 {vn_now_str()}"
        )
        await context.bot.send_message(chat_id, msg, reply_markup=main_keyboard())

# ===== health monitor & render keep-alive =====
async def health_probe(context: ContextTypes.DEFAULT_TYPE):
    if not _auto_on:
        return
    await _to_thread(health_ping, timeout=5)

# ===== text router =====
async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not guard(update): return
    txt = (update.message.text or "").strip().lower()

    if "trạng thái" in txt:
        return await status_cmd(update, context)
    if "auto" in txt:
        return await toggle_auto(update, context)
    if "test" in txt:
        return await test_cmd(update, context)
    if ("mexc" in txt) or ("đơn vị" in txt) or ("usd" in txt) or ("vnd" in txt):
        return await toggle_unit(update, context)

    await update.effective_chat.send_message("Mời chọn từ menu bên dưới.", reply_markup=main_keyboard())

# ===== build app & schedule =====
def build_app() -> Application:
    app: Application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), on_text))

    j = app.job_queue
    if j is None:
        # Phòng hờ nếu thiếu extras job-queue
        return app

    # 06:00 chào buổi sáng (nếu có file)
    if build_morning_text:
        async def _send_6h(ctx):
            if not ALLOWED_USER_ID: return
            text = await _to_thread(build_morning_text, _current_unit, "Trương", timeout=12)
            if text:
                await ctx.bot.send_message(ALLOWED_USER_ID, text)
        j.run_daily(_send_6h, time=dt_time(6, 0, tzinfo=VN_TZ))

    # 22:00 tổng kết (nếu có file)
    if build_night_message:
        async def _send_22h(ctx):
            if not ALLOWED_USER_ID: return
            text = await _to_thread(build_night_message, "Trương", timeout=8)
            if text:
                await ctx.bot.send_message(ALLOWED_USER_ID, text, parse_mode=ParseMode.MARKDOWN)
        j.run_daily(_send_22h, time=dt_time(22, 0, tzinfo=VN_TZ))

    # Slot 30’ + pre-notify 1 phút
    for hhmm in SLOT_TIMES:
        h, m = map(int, hhmm.split(":"))
        ph, pm = _time_minus_one_minute(h, m)
        j.run_daily(pre_notify,           time=dt_time(ph, pm, 0, tzinfo=VN_TZ))
        j.run_daily(send_batch_scalping,  time=dt_time(h,  m,  0, tzinfo=VN_TZ))

    # Health/keep-alive
    j.run_repeating(health_probe, interval=HEALTH_POLL_SEC, first=10)

    return app
