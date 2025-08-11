# -*- coding: utf-8 -*-
"""
Telegram bot — autiner (PRO)
Menu:
  H1: 🔎 Trạng thái | 🟢/🔴 Auto ON/OFF (đổi nhãn theo trạng thái)
  H2: 📅 Hôm nay | 📅 Ngày mai
  H3: 📅 Cả tuần | 🧪 Test
  H4: 💰 MEXC VND / 💵 MEXC USD (đổi nhãn theo đơn vị)
Slot: 06:15 → 21:45 (30’)
• Countdown 15s (chạy ở hh:mm:45 → hh:mm:00, để tránh xung đột lúc gửi tín hiệu).
"""

from __future__ import annotations
import asyncio
from datetime import datetime, timedelta, time as dt_time, date as dt_date
import pytz
from telegram import Update, ReplyKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application, ApplicationBuilder, CommandHandler,
    MessageHandler, ContextTypes, filters
)

from settings import (
    TELEGRAM_BOT_TOKEN, ALLOWED_USER_ID, TZ_NAME,
    SLOT_TIMES, NUM_SCALPING, HEALTH_POLL_SEC,
    DEFAULT_UNIT
)
from .mexc_api import smart_pick_signals, market_snapshot

VN_TZ = pytz.timezone(TZ_NAME)
_current_unit = DEFAULT_UNIT if DEFAULT_UNIT in ("VND", "USD") else "VND"
_auto_on = True

# ===== Helpers =====
def guard(update: Update) -> bool:
    return not (ALLOWED_USER_ID and update.effective_user and update.effective_user.id != ALLOWED_USER_ID)

def vn_now() -> datetime:
    return datetime.now(VN_TZ)

def vn_now_str() -> str:
    return vn_now().strftime("%H:%M %d/%m/%Y")

def weekday_vi(dt) -> str:
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

# ===== Nhãn tĩnh =====
BTN_STATUS   = "🔎 Trạng thái"
BTN_TODAY    = "📅 Hôm nay"
BTN_TOMORROW = "📅 Ngày mai"
BTN_WEEK     = "📅 Cả tuần"
BTN_TEST     = "🧪 Test"

# ===== Menu động =====
def main_keyboard() -> ReplyKeyboardMarkup:
    auto_lbl = "🟢 Auto ON" if _auto_on else "🔴 Auto OFF"
    unit_lbl = "💰 MEXC VND" if _current_unit == "VND" else "💵 MEXC USD"
    rows = [
        [BTN_STATUS, auto_lbl],
        [BTN_TODAY, BTN_TOMORROW],
        [BTN_WEEK, BTN_TEST],
        [unit_lbl],
    ]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)

# ===== Offload các tác vụ đồng bộ sang thread + timeout =====
async def _to_thread_signals(unit: str, n: int, timeout: int = 20):
    async def _run():
        return await asyncio.to_thread(smart_pick_signals, unit, n)
    try:
        return await asyncio.wait_for(_run(), timeout=timeout)
    except asyncio.TimeoutError:
        return None, None, False, None
    except Exception:
        return None, None, False, None

async def _to_thread_snapshot(topn: int = 1, timeout: int = 8):
    async def _run():
        return await asyncio.to_thread(market_snapshot, "USD", topn)
    try:
        return await asyncio.wait_for(_run(), timeout=timeout)
    except Exception:
        return [], False, 0.0

# ===== Commands =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not guard(update): return
    await update.effective_chat.send_message(
        "AUTINER đã sẵn sàng. Chọn từ menu bên dưới nhé.",
        reply_markup=main_keyboard()
    )

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not guard(update): return
    _, live, _ = await _to_thread_snapshot(topn=1)
    await update.effective_chat.send_message(
        f"📡 Trạng thái dữ liệu: {'LIVE ✅' if live else 'DOWN ❌'}\n"
        f"• Đơn vị hiện tại: {_current_unit}\n"
        f"• Auto: {'ON' if _auto_on else 'OFF'}",
        reply_markup=main_keyboard()
    )

# ===== Lịch (placeholder vĩ mô) =====
async def today_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not guard(update): return
    now = vn_now()
    text = (
        f"📅 Hôm nay: {weekday_vi(now)}, {now.strftime('%d/%m/%Y')}\n"
        "• Lịch vĩ mô: (sẽ bổ sung sau)."
    )
    await update.effective_chat.send_message(text, reply_markup=main_keyboard())

async def tomorrow_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not guard(update): return
    tm = vn_now() + timedelta(days=1)
    text = (
        f"📅 Ngày mai: {weekday_vi(tm)}, {tm.strftime('%d/%m/%Y')}\n"
        "• Lịch vĩ mô: (sẽ bổ sung sau)."
    )
    await update.effective_chat.send_message(text, reply_markup=main_keyboard())

async def week_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not guard(update): return
    lines = ["📅 Cả tuần (vĩ mô):", "• Chưa kết nối nguồn — sẽ bổ sung sau."]
    await update.effective_chat.send_message("\n".join(lines), reply_markup=main_keyboard())

# ===== Toggle =====
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

# ===== Nút Test: tạo tín hiệu ngay (không chặn loop) =====
async def test_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not guard(update): return
    await update.effective_chat.send_message("🧪 Đang tạo tín hiệu thử...", reply_markup=main_keyboard())

    signals, highlights, live, rate = await _to_thread_signals(_current_unit, NUM_SCALPING, timeout=20)
    if (not live) or (not signals):
        return await update.effective_chat.send_message("⚠️ Chưa đủ dữ liệu / nguồn chậm, thử lại sau.", reply_markup=main_keyboard())

    header = f"📌 (TEST) {len(signals)} lệnh — {vn_now_str()}"
    await update.effective_chat.send_message(header)
    for s in signals:
        side_icon = '🟩' if s['side']=='LONG' else '🟥'
        msg = (
            f"📈 {s['token']} ({s['unit']}) — {side_icon} {s['side']} | {s['orderType'].upper()}\n\n"
            f"💰 Entry: {s['entry']}\n"
            f"🎯 TP: {s['tp']}    🛡️ SL: {s['sl']}\n"
            f"📊 Độ mạnh: {s['strength']}%\n"
            f"📌 Lý do:\n{s['reason']}"
        )
        await update.effective_chat.send_message(msg, reply_markup=main_keyboard())

# ===== Countdown 15s trước slot =====
async def pre_countdown(context: ContextTypes.DEFAULT_TYPE):
    if not _auto_on:
        return
    chat_id = ALLOWED_USER_ID
    try:
        msg = await context.bot.send_message(
            chat_id,
            "⏳ Tín hiệu 30’ **tiếp theo** — còn 15s",
            parse_mode=ParseMode.MARKDOWN
        )
        for sec in range(14, -1, -1):
            if sec <= 1:
                break
            await asyncio.sleep(1)
            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id, message_id=msg.message_id,
                    text=f"⏳ Tín hiệu 30’ **tiếp theo** — còn {sec:02d}s",
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception:
                pass
    except Exception:
        return

# ===== Batch tín hiệu (không chặn loop) =====
async def send_batch_scalping(context: ContextTypes.DEFAULT_TYPE):
    if not _auto_on:
        return
    chat_id = ALLOWED_USER_ID

    signals, highlights, live, rate = await _to_thread_signals(_current_unit, NUM_SCALPING, timeout=25)
    if (not live) or (not signals):
        now = vn_now()
        nxt_hhmm, mins = next_slot_info(now)
        return await context.bot.send_message(
            chat_id,
            f"⚠️ Slot {now.strftime('%H:%M')} không có dữ liệu đủ/kịp để tạo tín hiệu.\n"
            f"🗓️ Dự kiến slot kế tiếp **{nxt_hhmm}** (~{mins}’).",
            reply_markup=main_keyboard()
        )

    header = f"📌 Tín hiệu {len(signals)} lệnh (Scalping) — {vn_now_str()}"
    await context.bot.send_message(chat_id, header)

    for s in signals:
        side_icon = '🟩' if s['side']=='LONG' else '🟥'
        msg = (
            f"📈 {s['token']} ({s['unit']}) — {side_icon} {s['side']} | {s['orderType'].upper()}\n\n"
            f"💰 Entry: {s['entry']}\n"
            f"🎯 TP: {s['tp']}    🛡️ SL: {s['sl']}\n"
            f"📊 Độ mạnh: {s['strength']}%  |  Khung: 1–5m\n"
            f"📌 Lý do (MA/RSI):\n{s['reason']}\n"
            f"🕒 {vn_now_str()}"
        )
        await context.bot.send_message(chat_id, msg, reply_markup=main_keyboard())

# ===== Health monitor (không chặn loop) =====
async def health_probe(context: ContextTypes.DEFAULT_TYPE):
    if not _auto_on:
        return
    chat_id = ALLOWED_USER_ID
    try:
        coins, live, _ = await _to_thread_snapshot(topn=1, timeout=8)
        if not live or not coins:
            now = vn_now()
            nxt_hhmm, mins = next_slot_info(now)
            await context.bot.send_message(
                chat_id,
                f"🚨 Dữ liệu MEXC chậm hoặc gián đoạn lúc {now.strftime('%H:%M')}.\n"
                f"↪️ Sẽ thử lại trước slot **{nxt_hhmm}** (~{mins}’).",
                reply_markup=main_keyboard()
            )
    except Exception:
        pass

# ===== Text router =====
async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not guard(update): return
    txt = (update.message.text or "").strip().lower()

    if "trạng thái" in txt:
        return await status_cmd(update, context)
    if "auto" in txt:
        return await toggle_auto(update, context)
    if "hôm nay" in txt:
        return await today_cmd(update, context)
    if "ngày mai" in txt:
        return await tomorrow_cmd(update, context)
    if "cả tuần" in txt:
        return await week_cmd(update, context)
    if "test" in txt:
        return await test_cmd(update, context)
    if "mexc" in txt or "đơn vị" in txt or "usd" in txt or "vnd" in txt:
        return await toggle_unit(update, context)

    await update.effective_chat.send_message("Mời chọn từ menu bên dưới.", reply_markup=main_keyboard())

# ===== Build app & schedule =====
def build_app() -> Application:
    app: Application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), on_text))

    j = app.job_queue
    for hhmm in SLOT_TIMES:
        h, m = map(int, hhmm.split(":"))
        # countdown 15s: chạy lúc hh:mm:45
        j.run_daily(pre_countdown,       time=dt_time(h, m, 45, tzinfo=VN_TZ))
        # gửi tín hiệu đúng hh:mm:00
        j.run_daily(send_batch_scalping, time=dt_time(h, m, 0,  tzinfo=VN_TZ))

    j.run_repeating(health_probe, interval=HEALTH_POLL_SEC, first=10)
    return app
