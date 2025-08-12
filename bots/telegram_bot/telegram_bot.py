# -*- coding: utf-8 -*-
"""
Telegram bot — Autiner
- Menu: Trạng thái | Auto ON/OFF | Test | MEXC VND/USD
- Countdown 15s trước slot | Gửi batch tín hiệu
- Gọi morning_report & night_summary nếu bạn đã thêm vào project
"""

from __future__ import annotations
import asyncio
from datetime import datetime, timedelta, time as dt_time
import pytz
from telegram import Update, ReplyKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application, ApplicationBuilder, CommandHandler,
    MessageHandler, ContextTypes, filters
)

from settings import (
    TELEGRAM_BOT_TOKEN, ALLOWED_USER_ID, TZ_NAME,
    SLOT_TIMES, NUM_SCALPING, HEALTH_POLL_SEC, DEFAULT_UNIT
)

# ONUS price + MEXC api
from ..pricing.onus_format import display_price
from .mexc_api import smart_pick_signals, market_snapshot

# (tuỳ bạn đã thêm)
try:
    from ..pricing.morning_report import send_morning_report
    from ..pricing.night_summary import send_night_summary
except Exception:
    send_morning_report = None
    send_night_summary  = None

VN_TZ = pytz.timezone(TZ_NAME)
_current_unit = DEFAULT_UNIT if DEFAULT_UNIT in ("VND","USD") else "VND"
_auto_on = True

# ===== Helpers =====
def guard(update: Update) -> bool:
    return not (ALLOWED_USER_ID and update.effective_user and update.effective_user.id != ALLOWED_USER_ID)

def vn_now() -> datetime:
    return datetime.now(VN_TZ)

def vn_now_str() -> str:
    return vn_now().strftime("%H:%M %d/%m/%Y")

def next_slot_info(now: datetime) -> tuple[str, int]:
    today = now.date()
    slots = []
    for hhmm in SLOT_TIMES:
        h, m = map(int, hhmm.split(":"))
        slots.append(VN_TZ.localize(datetime.combine(today, dt_time(h, m))))
    future = [s for s in slots if s > now]
    nxt = future[0] if future else VN_TZ.localize(datetime.combine(today+timedelta(days=1),
                                                                 dt_time(*map(int, SLOT_TIMES[0].split(":")))))
    mins = max(0, int((nxt - now).total_seconds() // 60))
    return nxt.strftime("%H:%M"), mins

# ===== Labels =====
BTN_STATUS = "🔎 Trạng thái"
BTN_TEST   = "🧪 Test"

def main_keyboard() -> ReplyKeyboardMarkup:
    auto_lbl = "🟢 Auto ON" if _auto_on else "🔴 Auto OFF"
    unit_lbl = "💰 MEXC VND" if _current_unit == "VND" else "💵 MEXC USD"
    rows = [[BTN_STATUS, auto_lbl], [BTN_TEST, unit_lbl]]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)

# ===== Offload heavy tasks =====
async def _to_thread_signals(unit: str, n: int, timeout: int = 25):
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
        return await asyncio.to_thread(market_snapshot, _current_unit, topn)
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
    coins, live, rate = await _to_thread_snapshot(topn=3)
    lines = []
    for c in coins:
        lines.append(f"- {c['display']}: {c['price_str']} {_current_unit} ({c['chg']:+.2f}%)")
    txt = (
        f"📡 Dữ liệu: {'LIVE ✅' if live else 'DOWN ❌'}\n"
        f"• Đơn vị: {_current_unit}\n"
        f"• Auto: {'ON' if _auto_on else 'OFF'}\n"
        f"• USD/VND ≈ {rate:,.2f}\n"
        + ("\n".join(lines) if lines else "")
    ).replace(",", "X").replace(".", ",").replace("X",".")
    await update.effective_chat.send_message(txt, reply_markup=main_keyboard())

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
        f"💱 Đã chuyển sang **{_current_unit}**",
        parse_mode=ParseMode.MARKDOWN, reply_markup=main_keyboard()
    )

async def test_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not guard(update): return
    await update.effective_chat.send_message("🧪 Đang tạo tín hiệu thử...", reply_markup=main_keyboard())
    signals, highlights, live, rate = await _to_thread_signals(_current_unit, NUM_SCALPING)
    if (not live) or (not signals):
        return await update.effective_chat.send_message("⚠️ Chưa đủ dữ liệu / nguồn chậm, thử lại sau.", reply_markup=main_keyboard())

    header = f"📌 (TEST) {len(signals)} lệnh — {vn_now_str()}"
    await update.effective_chat.send_message(header)
    for s in signals:
        side_icon = '🟩' if s['side']=='LONG' else '🟥'
        msg = (
            f"📈 {s['token']} ({s['unit']}) — {side_icon} {s['side']} | {s['orderType']}\n\n"
            f"💰 Entry: {s['entry']}\n"
            f"🎯 TP: {s['tp']}    🛡️ SL: {s['sl']}\n"
            f"📊 Độ mạnh: {s['strength']}%  |  Khung: 1–5m\n"
            f"📌 Lý do:\n{s['reason']}"
        )
        await update.effective_chat.send_message(msg, reply_markup=main_keyboard())

# ===== Countdown 15s trước slot =====
async def pre_countdown(context: ContextTypes.DEFAULT_TYPE):
    if not _auto_on: return
    chat_id = ALLOWED_USER_ID
    try:
        msg = await context.bot.send_message(chat_id, "⏳ Tín hiệu 30’ **tiếp theo** — còn 15s", parse_mode=ParseMode.MARKDOWN)
        for sec in range(14, -1, -1):
            if sec <= 1: break
            await asyncio.sleep(1)
            try:
                await context.bot.edit_message_text(chat_id=chat_id, message_id=msg.message_id,
                    text=f"⏳ Tín hiệu 30’ **tiếp theo** — còn {sec:02d}s", parse_mode=ParseMode.MARKDOWN)
            except Exception:
                pass
    except Exception:
        return

# ===== Gửi batch scalping =====
async def send_batch_scalping(context: ContextTypes.DEFAULT_TYPE):
    if not _auto_on: return
    chat_id = ALLOWED_USER_ID
    signals, highlights, live, rate = await _to_thread_signals(_current_unit, NUM_SCALPING)
    if (not live) or (not signals):
        now = vn_now()
        nxt_hhmm, mins = next_slot_info(now)
        return await context.bot.send_message(
            chat_id,
            f"⚠️ Slot {now.strftime('%H:%M')} chưa có tín hiệu do dữ liệu. Hẹn slot **{nxt_hhmm}** (~{mins}’).",
            reply_markup=main_keyboard()
        )

    header = f"📌 Tín hiệu {len(signals)} lệnh (Scalping) — {vn_now_str()}"
    await context.bot.send_message(chat_id, header)
    for s in signals:
        side_icon = '🟩' if s['side']=='LONG' else '🟥'
        msg = (
            f"📈 {s['token']} ({s['unit']}) — {side_icon} {s['side']} | {s['orderType']}\n\n"
            f"💰 Entry: {s['entry']}\n"
            f"🎯 TP: {s['tp']}    🛡️ SL: {s['sl']}\n"
            f"📊 Độ mạnh: {s['strength']}%  |  Khung: 1–5m\n"
            f"📌 Lý do:\n{s['reason']}\n"
            f"🕒 {vn_now_str()}"
        )
        await context.bot.send_message(chat_id, msg, reply_markup=main_keyboard())

# ===== Health monitor =====
async def health_probe(context: ContextTypes.DEFAULT_TYPE):
    if not _auto_on: return
    chat_id = ALLOWED_USER_ID
    try:
        coins, live, rate = await _to_thread_snapshot(topn=1)
        if not live or not coins:
            now = vn_now()
            nxt_hhmm, mins = next_slot_info(now)
            await context.bot.send_message(
                chat_id,
                f"🚨 Dữ liệu MEXC chậm lúc {now.strftime('%H:%M')}. Sẽ thử lại trước slot **{nxt_hhmm}** (~{mins}’).",
                reply_markup=main_keyboard()
            )
    except Exception:
        pass

# ===== Router =====
async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not guard(update): return
    txt = (update.message.text or "").lower().strip()
    if "trạng thái" in txt:  return await status_cmd(update, context)
    if "auto" in txt:        return await toggle_auto(update, context)
    if "test" in txt:        return await test_cmd(update, context)
    if "mexc" in txt or "đơn vị" in txt or "usd" in txt or "vnd" in txt:
        return await toggle_unit(update, context)
    await update.effective_chat.send_message("Mời chọn từ menu bên dưới.", reply_markup=main_keyboard())

# ===== Build app & schedule =====
def build_app() -> Application:
    app: Application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("test", test_cmd))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), on_text))

    j = app.job_queue
    for hhmm in SLOT_TIMES:
        h, m = map(int, hhmm.split(":"))
        j.run_daily(pre_countdown,       time=dt_time(h, m, 45, tzinfo=VN_TZ))
        j.run_daily(send_batch_scalping, time=dt_time(h, m,  0, tzinfo=VN_TZ))

    # sáng & tối (nếu bạn đã thêm file)
    if send_morning_report:
        j.run_daily(send_morning_report, time=dt_time(6, 0, 0, tzinfo=VN_TZ))
    if send_night_summary:
        j.run_daily(send_night_summary,  time=dt_time(22, 0, 0, tzinfo=VN_TZ))

    j.run_repeating(health_probe, interval=HEALTH_POLL_SEC, first=10)
    return app
