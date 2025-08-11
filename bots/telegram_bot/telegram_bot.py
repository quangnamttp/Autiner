# -*- coding: utf-8 -*-
"""
Telegram bot — autiner (bản PRO, lý do theo MA/RSI)
Menu:
  H1: 🔎 Trạng thái | 🟢/🔴 Auto ON/OFF (đổi nhãn theo trạng thái)
  H2: 📅 Hôm nay | 📅 Ngày mai
  H3: 📅 Cả tuần | 📜 Lịch vạn niên
  H4: 💰 MEXC VND / 💵 MEXC USD (đổi nhãn theo đơn vị) | 🧪 Test
Slot: 06:15 → 21:45 (30’), countdown 60s.
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

# Lịch âm (tuỳ chọn)
try:
    from lunardate import LunarDate
    HAS_LUNAR = True
except Exception:
    HAS_LUNAR = False

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

def weekday_vi(dt: datetime | dt_date) -> str:
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

# ===== Nhãn nút tĩnh (không phụ thuộc trạng thái) =====
BTN_STATUS   = "🔎 Trạng thái"
BTN_TODAY    = "📅 Hôm nay"
BTN_TOMORROW = "📅 Ngày mai"
BTN_WEEK     = "📅 Cả tuần"
BTN_LUNAR    = "📜 Lịch vạn niên"
BTN_TEST     = "🧪 Test"

# ===== Menu động theo trạng thái =====
def main_keyboard() -> ReplyKeyboardMarkup:
    auto_lbl = "🟢 Auto ON" if _auto_on else "🔴 Auto OFF"
    unit_lbl = "💰 MEXC VND" if _current_unit == "VND" else "💵 MEXC USD"
    rows = [
        [BTN_STATUS, auto_lbl],
        [BTN_TODAY, BTN_TOMORROW],
        [BTN_WEEK, BTN_LUNAR],
        [unit_lbl, BTN_TEST],
    ]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)

# ===== Commands =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not guard(update): return
    await update.effective_chat.send_message(
        "AUTINER đã sẵn sàng. Chọn từ menu bên dưới nhé.",
        reply_markup=main_keyboard()
    )

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not guard(update): return
    _, live, _ = market_snapshot(unit="USD", topn=1)
    await update.effective_chat.send_message(
        f"📡 Trạng thái dữ liệu: {'LIVE ✅' if live else 'DOWN ❌'}\n"
        f"• Đơn vị hiện tại: {_current_unit}\n"
        f"• Auto: {'ON' if _auto_on else 'OFF'}",
        reply_markup=main_keyboard()
    )

# ===== Lịch vạn niên =====
def _lunar_line(d: dt_date) -> str:
    if not HAS_LUNAR:
        return "• (Chưa cài 'lunardate' — thêm 'lunardate==0.2.0' vào requirements.txt để xem Âm lịch)"
    ld = LunarDate.fromSolarDate(d.year, d.month, d.day)
    return f"Âm lịch: {ld.day}/{ld.month}/{ld.year} (AL)"

async def today_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not guard(update): return
    now = vn_now()
    text = f"📅 Hôm nay: {weekday_vi(now)}, {now.strftime('%d/%m/%Y')}\n{_lunar_line(now.date())}"
    await update.effective_chat.send_message(text, reply_markup=main_keyboard())

async def tomorrow_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not guard(update): return
    tm = vn_now() + timedelta(days=1)
    text = f"📅 Ngày mai: {weekday_vi(tm)}, {tm.strftime('%d/%m/%Y')}\n{_lunar_line(tm.date())}"
    await update.effective_chat.send_message(text, reply_markup=main_keyboard())

async def week_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not guard(update): return
    base = vn_now().date()
    lines = ["📅 Cả tuần:"]
    start = base - timedelta(days=base.weekday())  # Thứ Hai
    for i in range(7):
        d = start + timedelta(days=i)
        lines.append(f"- {weekday_vi(d)}, {d.strftime('%d/%m/%Y')} — {_lunar_line(d)}")
    await update.effective_chat.send_message("\n".join(lines), reply_markup=main_keyboard())

async def lunar_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not guard(update): return
    msg = (
        "📜 Lịch vạn niên\n"
        "• Bấm '📅 Hôm nay' hoặc '📅 Ngày mai' để xem nhanh.\n"
        "• Hoặc nhắn: lich dd/mm/yyyy (ví dụ: lich 12/08/2025)."
    )
    await update.effective_chat.send_message(msg, reply_markup=main_keyboard())

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

# ===== Countdown trước slot =====
async def pre_countdown(context: ContextTypes.DEFAULT_TYPE):
    if not _auto_on:
        return
    chat_id = ALLOWED_USER_ID
    msg = await context.bot.send_message(chat_id, "⏳ Tín hiệu 30’ **tiếp theo** — còn 60s", parse_mode=ParseMode.MARKDOWN)
    for sec in range(59, -1, -1):
        try:
            await asyncio.sleep(1)
            await context.bot.edit_message_text(
                chat_id=chat_id, message_id=msg.message_id,
                text=f"⏳ Tín hiệu 30’ **tiếp theo** — còn {sec:02d}s",
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception:
            break

# ===== Batch tín hiệu =====
async def send_batch_scalping(context: ContextTypes.DEFAULT_TYPE):
    if not _auto_on:
        return
    chat_id = ALLOWED_USER_ID
    try:
        signals, highlights, live, rate = smart_pick_signals(_current_unit, NUM_SCALPING)
    except Exception as e:
        await context.bot.send_message(chat_id, f"⚠️ Lỗi tạo tín hiệu: {e}", reply_markup=main_keyboard())
        return

    if (not live) or (not signals):
        now = vn_now()
        nxt_hhmm, mins = next_slot_info(now)
        await context.bot.send_message(
            chat_id,
            f"⚠️ Slot {now.strftime('%H:%M')} không có dữ liệu đủ/kịp để tạo tín hiệu.\n"
            f"↪️ Dự kiến slot kế tiếp **{nxt_hhmm}** (~{mins}’).",
            reply_markup=main_keyboard()
        )
        return

    header = f"📌 Tín hiệu {len(signals)} lệnh (Scalping) — {vn_now_str()}"
    await context.bot.send_message(chat_id, header)

    for s in signals:
        side_icon = '🟩' if s['side']=='LONG' else '🟥'
        msg = (
            f"📈 {s['token']} ({s['unit']}) — {side_icon} {s['side']} | Chiến lược: {s['orderType'].upper()}\n\n"
            f"💰 Entry: {s['entry']}\n"
            f"🎯 TP: {s['tp']}    🛡️ SL: {s['sl']}\n"
            f"📊 Độ mạnh: {s['strength']}%  |  Khung: 1–5m\n"
            f"📌 Lý do (MA/RSI):\n{s['reason']}\n"
            f"🕒 {vn_now_str()}"
        )
        await context.bot.send_message(chat_id, msg, reply_markup=main_keyboard())

# ===== Health monitor =====
async def health_probe(context: ContextTypes.DEFAULT_TYPE):
    if not _auto_on:
        return
    chat_id = ALLOWED_USER_ID
    try:
        coins, live, _ = market_snapshot(unit="USD", topn=1)
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
    txt = (update.message.text or "").strip()

    # Bắt theo từ khoá để nhãn có đổi vẫn hoạt động
    low = txt.lower()
    if "trạng thái" in low:
        return await status_cmd(update, context)
    if "auto" in low:
        return await toggle_auto(update, context)
    if "hôm nay" in low:
        return await today_cmd(update, context)
    if "ngày mai" in low:
        return await tomorrow_cmd(update, context)
    if "cả tuần" in low:
        return await week_cmd(update, context)
    if "vạn niên" in low:
        return await lunar_menu(update, context)
    if "mexc" in low or "đơn vị" in low or "usd" in low or "vnd" in low:
        return await toggle_unit(update, context)
    if low.startswith("lich "):
        try:
            # lich dd/mm/yyyy
            _, dstr = low.split(" ", 1)
            dd, mm, yy = dstr.split("/")
            d = dt_date(int(yy), int(mm), int(dd))
            msg = f"📅 {weekday_vi(d)}, {d.strftime('%d/%m/%Y')}\n{_lunar_line(d)}"
        except Exception:
            msg = "❗ Cú pháp: lich dd/mm/yyyy (ví dụ: lich 12/08/2025)"
        return await update.effective_chat.send_message(msg, reply_markup=main_keyboard())

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
        mm = (m - 1) % 60
        hh = h if m > 0 else (h - 1)
        j.run_daily(pre_countdown,       time=dt_time(hh, mm, tzinfo=VN_TZ))
        j.run_daily(send_batch_scalping, time=dt_time(h,  m, tzinfo=VN_TZ))

    j.run_repeating(health_probe, interval=HEALTH_POLL_SEC, first=10)
    return app
