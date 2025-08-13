# bots/telegram_bot/telegram_bot.py
# -*- coding: utf-8 -*-
"""
Autiner Telegram Bot (v2, webhook-friendly)
- Menu: 🔎 Trạng thái | 🟢/🔴 Auto ON/OFF | 🧪 Test | 💰/💵 đổi đơn vị
- Slot: 06:15 → 21:45 mỗi 30' (THÔNG BÁO trước ~1 phút)
- Gọi: morning_report (06:00) & night_summary (22:00)
- Không block event-loop: tác vụ nặng chạy trong thread + timeout
- Có lệnh chẩn đoán: /diag
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

# ===== settings =====
from settings import (
    TELEGRAM_BOT_TOKEN, ALLOWED_USER_ID, TZ_NAME,
    SLOT_TIMES, NUM_SCALPING, HEALTH_POLL_SEC,
    DEFAULT_UNIT, VOL24H_FLOOR, BREAK_VOL_MULT, FUNDING_ABS_LIM,
    DIVERSITY_POOL_TOPN
)

# ===== domain modules =====
# 06:00 & 22:00
try:
    from bots.pricing.morning_report import build_morning_text
except Exception:
    build_morning_text = None

try:
    from bots.pricing.night_summary import build_night_message
except Exception:
    build_night_message = None

# MEXC client
from bots.mexc_client import fetch_tickers, get_usd_vnd_rate, health_ping

# ===== Signal Engine =====
_signal_fn = None
try:
    # Trả (signals, highlights, live, rate) hoặc list[signals]
    from bots.signals.signal_engine import generate_scalping_signals as _signal_fn
except Exception:
    _signal_fn = None

def _call_signals(unit: str, n: int):
    """Bọc kết quả trả về từ engine."""
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

def _pre_time(h: int, m: int) -> tuple[int, int]:
    """Thời điểm trước 1 phút cho lịch thông báo."""
    if m > 0:
        return h, m - 1
    return (h - 1) % 24, 59

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
    """Test: gửi 06:00 + tạo 1 batch tín hiệu ngay."""
    if not guard(update): return
    chat_id = update.effective_chat.id

    # 06:00 sample
    if build_morning_text:
        text6 = await _to_thread(build_morning_text, _current_unit, "Trương", timeout=12)
        if text6:
            await context.bot.send_message(chat_id, text6)

    # tín hiệu
    sigs = await _to_thread(_call_signals, _current_unit, NUM_SCALPING, timeout=28)
    if not sigs:
        await context.bot.send_message(chat_id, "⚠️ Chưa đủ dữ liệu / engine trả rỗng.", reply_markup=main_keyboard())
        return

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

# ===== thông báo trước slot ~1 phút =====
async def pre_notify_next_slot(context: ContextTypes.DEFAULT_TYPE):
    if not _auto_on:
        return
    chat_id = ALLOWED_USER_ID
    try:
        await context.bot.send_message(
            chat_id,
            "⏳ Tín hiệu 30’ sắp diễn ra trong ~1 phút.\nVui lòng chuẩn bị khối lượng & kỷ luật vào lệnh.",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception:
        return

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
            f"⚠️ Slot {now.strftime('%H:%M')} không đủ dữ liệu để tạo tín hiệu.\n"
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

# ===== health monitor & keep-alive =====
async def health_probe(context: ContextTypes.DEFAULT_TYPE):
    if not _auto_on:
        return
    await _to_thread(health_ping, timeout=5)

# ===== DIAGNOSTICS =====
try:
    from bots.signals.signal_engine import market_snapshot as _se_snapshot
except Exception:
    _se_snapshot = None

async def diag_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lệnh /diag: hiển thị tình trạng engine & nguồn dữ liệu."""
    if not guard(update): return
    engine_ok = (_signal_fn is not None)
    ticks = await _to_thread(fetch_tickers, timeout=10)
    n_ticks = len(ticks or [])
    msg = [f"🔧 DIAG:",
           f"• Engine import: {'OK ✅' if engine_ok else '❌ NONE'}",
           f"• fetch_tickers(): {n_ticks} items"]
    if _se_snapshot:
        res = await _to_thread(_se_snapshot, "USD", DIVERSITY_POOL_TOPN, timeout=12)
        try:
            coins, live, rate = res
        except Exception:
            coins, live, rate = [], False, 0.0
        msg.append(f"• market_snapshot: live={live} | after-liquidity={len(coins)} | FX≈{rate:,.0f} VND")
        for d in (coins or [])[:5]:
            msg.append(f"  - {d['symbol']}: qv={d.get('volumeQuote',0.0):.0f} | chg={d.get('change24h_pct',0.0):+.1f}% | fr={d.get('fundingRate',0.0):+.3f}%")
    msg.append(f"• thresholds: VOL_FLOOR={VOL24H_FLOOR:.0f} | BREAKx={BREAK_VOL_MULT} | |FR|<{FUNDING_ABS_LIM}")
    await update.effective_chat.send_message("\n".join(msg))

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
    if ("diag" in txt) or ("chẩn đoán" in txt):
        return await diag_cmd(update, context)

    await update.effective_chat.send_message("Mời chọn từ menu bên dưới.", reply_markup=main_keyboard())

# ===== build app & schedule =====
def build_app() -> Application:
    app: Application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("test", test_cmd))   # cho phép /test
    app.add_handler(CommandHandler("diag", diag_cmd))   # cho phép /diag

    # Texts
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), on_text))

    # Jobs (nếu cài job-queue)
    j = app.job_queue
    if j is not None:
        # 06:00 chào buổi sáng
        if build_morning_text:
            async def _send_6h(ctx):
                if not ALLOWED_USER_ID: return
                text = await _to_thread(build_morning_text, _current_unit, "Trương", timeout=12)
                if text:
                    await ctx.bot.send_message(ALLOWED_USER_ID, text)
            j.run_daily(_send_6h, time=dt_time(6, 0, tzinfo=VN_TZ))

        # 22:00 tổng kết
        if build_night_message:
            async def _send_22h(ctx):
                if not ALLOWED_USER_ID: return
                text = await _to_thread(build_night_message, "Trương", timeout=8)
                if text:
                    await ctx.bot.send_message(ALLOWED_USER_ID, text, parse_mode=ParseMode.MARKDOWN)
            j.run_daily(_send_22h, time=dt_time(22, 0, tzinfo=VN_TZ))

        # Slot 30’ + pre-notify ~1 phút
        for hhmm in SLOT_TIMES:
            h, m = map(int, hhmm.split(":"))
            ph, pm = _pre_time(h, m)
            j.run_daily(pre_notify_next_slot, time=dt_time(ph, pm, 0, tzinfo=VN_TZ))
            j.run_daily(send_batch_scalping,  time=dt_time(h,  m,  0, tzinfo=VN_TZ))

        # Health/keep-alive
        j.run_repeating(health_probe, interval=HEALTH_POLL_SEC, first=10)

    return app
