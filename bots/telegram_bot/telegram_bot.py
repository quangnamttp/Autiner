# bots/telegram_bot/telegram_bot.py

import asyncio
import time
import pytz
from datetime import datetime, time as dt_time, timedelta

from telegram import Update, ReplyKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application, ApplicationBuilder, CommandHandler,
    MessageHandler, ContextTypes, filters
)

from settings import (
    TELEGRAM_BOT_TOKEN, ALLOWED_USER_ID, TZ_NAME,
    DEFAULT_UNIT, SLOT_TIMES, NUM_SCALPING,
    FAIL_ALERT_COOLDOWN_SEC, HEALTH_POLL_SEC,
)

# === data source (MEXC) ===
from .mexc_api import smart_pick_signals, market_snapshot

# ================== TIME & GUARD ==================
VN_TZ = pytz.timezone(TZ_NAME)

def guard(update: Update) -> bool:
    """Allow only configured user."""
    return not (ALLOWED_USER_ID and update.effective_user
                and update.effective_user.id != ALLOWED_USER_ID)

def vn_now_str():
    return datetime.now(VN_TZ).strftime("%H:%M %d/%m/%Y")

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
    nxt = future[0] if future else VN_TZ.localize(
        datetime.combine(today + timedelta(days=1),
                         dt_time(*map(int, SLOT_TIMES[0].split(":"))))
    )
    mins = max(0, int((nxt - now).total_seconds() // 60))
    return nxt.strftime("%H:%M"), mins

# ================== UI LABELS & STATE ==================
BTN_STATUS   = "🔎 Trạng thái"
BTN_TODAY    = "📅 Hôm nay"
BTN_TOMORROW = "📅 Ngày mai"
BTN_WEEK     = "📅 Cả tuần"
BTN_TEST     = "🧪 Test"
BTN_VND      = "💰 MEXC VND"
BTN_USD      = "💵 MEXC USD"
BTN_ON       = "🟢 Auto ON"
BTN_OFF      = "🔴 Auto OFF"

_current_unit = DEFAULT_UNIT  # "VND" | "USD"
_auto_enabled = True          # trạng thái ON/OFF gửi tự động

def _status_btn_text() -> str:
    return f"{BTN_STATUS} ({'ON' if _auto_enabled else 'OFF'})"

def _kbd() -> ReplyKeyboardMarkup:
    # 4 hàng theo layout bạn yêu cầu
    rows = [
        [ _status_btn_text(), BTN_TEST ],
        [ BTN_TODAY, BTN_TOMORROW ],
        [ BTN_WEEK,  BTN_VND ],
        [ BTN_USD, (BTN_OFF if _auto_enabled else BTN_ON) ],
    ]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)

# ================== COMMANDS ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not guard(update): return
    # Không gửi block mô tả dài — chỉ hiện menu
    await update.effective_chat.send_message(
        "Chọn thao tác bên dưới.", reply_markup=_kbd()
    )

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not guard(update): return
    coins, live, _ = await _probe_live()
    txt = (
        "📡 Trạng thái bot\n"
        "• Nguồn: MEXC Futures\n"
        f"• Kết nối: {'LIVE ✅' if live else 'DOWN ❌'}\n"
        f"• Tự động: {'ON 🟢' if _auto_enabled else 'OFF 🔴'}\n"
        f"• Đơn vị: {_current_unit}"
    )
    await update.effective_chat.send_message(txt, reply_markup=_kbd())

async def _probe_live():
    # gọi nhanh 1 snapshot mỏng
    coins, live, rate = market_snapshot(unit="USD", topn=1)
    return coins, live, rate

# ============== LỊCH VĨ MÔ (placeholder rút gọn) ==============
async def macro_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not guard(update): return
    now = datetime.now(VN_TZ)
    wd = weekday_vi(now)
    await update.effective_chat.send_message(
        f"📅 {wd}, {now.strftime('%d/%m/%Y')}\n"
        "• Lịch vĩ mô hôm nay (rút gọn).",
        reply_markup=_kbd()
    )

async def macro_tomorrow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not guard(update): return
    tmr = datetime.now(VN_TZ) + timedelta(days=1)
    wd = weekday_vi(tmr)
    await update.effective_chat.send_message(
        f"📅 {wd}, {tmr.strftime('%d/%m/%Y')}\n"
        "• Lịch vĩ mô ngày mai (rút gọn).",
        reply_markup=_kbd()
    )

async def macro_week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not guard(update): return
    await update.effective_chat.send_message(
        "📅 Lịch vĩ mô cả tuần (rút gọn).",
        reply_markup=_kbd()
    )

# ============== UNIT & AUTO TOGGLES ==============
async def _set_unit(update, context, unit: str):
    global _current_unit
    _current_unit = unit
    await update.effective_chat.send_message(
        f"✅ Đã chuyển đơn vị sang **{unit}**.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_kbd()
    )

async def _set_auto(update, context, enable: bool):
    global _auto_enabled
    _auto_enabled = enable
    await update.effective_chat.send_message(
        f"{'🟢' if enable else '🔴'} ĐÃ {'BẬT' if enable else 'TẮT'} gửi tín hiệu tự động (mỗi 30’).",
        reply_markup=_kbd()
    )

# ============== TEST COUNTDOWN (demo) ==============
async def pre_countdown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not guard(update): return
    chat_id = update.effective_chat.id
    msg = await context.bot.send_message(chat_id, "⏳ Tín hiệu 30’ **tiếp theo** — còn 60s",
                                         parse_mode=ParseMode.MARKDOWN,
                                         reply_markup=_kbd())
    for sec in range(59, -1, -1):
        try:
            await asyncio.sleep(1)
            await context.bot.edit_message_text(
                chat_id=chat_id, message_id=msg.message_id,
                text=f"⏳ Tín hiệu 30’ **tiếp theo** — còn {sec:02d}s",
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception:
            pass

# ============== SCHEDULED JOBS (06:00/07:00 + mỗi 30’) ==============
async def morning_brief(context: ContextTypes.DEFAULT_TYPE):
    chat_id = ALLOWED_USER_ID
    now = datetime.now(VN_TZ)
    wd = weekday_vi(now)
    coins, live, _ = market_snapshot(unit="USD", topn=30)
    if not live or not coins:
        await context.bot.send_message(chat_id, "⚠️ 06:00 không có dữ liệu LIVE để tạo bản tin sáng.")
        return
    # Tóm tắt nhanh
    long_votes = sum(1 for c in coins if c.get("change24h_pct",0)>=0 and c.get("fundingRate",0)>-0.02)
    long_pct = int(round(long_votes * 100 / max(1, len(coins))))
    short_pct = 100 - long_pct

    lines = [
        "Chào buổi sáng nhé anh Trương ☀️",
        f"Hôm nay: {wd}, {now.strftime('%H:%M %d/%m/%Y')}",
        "\nThị trường: nghiêng về " + ("LONG" if long_pct >= short_pct else "SHORT") +
        f" (Long {long_pct}% | Short {short_pct}%)",
        "• Tín hiệu tổng hợp: funding cân bằng, ưu tiên mid-cap.",
        "\nChờ tín hiệu 30’ đầu tiên lúc 06:15 (mình sẽ đếm ngược trước 60s).",
        "Chúc anh một ngày trade thật thành công! 🍀"
    ]
    await context.bot.send_message(chat_id, "\n".join(lines))

async def macro_daily(context: ContextTypes.DEFAULT_TYPE):
    chat_id = ALLOWED_USER_ID
    await context.bot.send_message(
        chat_id, "📅 Lịch vĩ mô hôm nay (rút gọn)."
    )

async def send_batch_scalping(context: ContextTypes.DEFAULT_TYPE):
    """Gửi 1 batch tín hiệu ở mỗi slot, có tôn trọng Auto ON/OFF."""
    if not _auto_enabled:
        return
    chat_id = ALLOWED_USER_ID
    signals, highlights, live, rate = smart_pick_signals(_current_unit, NUM_SCALPING)

    if (not live) or (not signals):
        now_vn = datetime.now(VN_TZ)
        nxt_hhmm, mins = next_slot_info(now_vn)
        await context.bot.send_message(
            chat_id,
            f"⚠️ Hệ thống đang gặp sự cố nên **slot {now_vn.strftime('%H:%M')}** không có tín hiệu.\n"
            f"↪️ Dự kiến hoạt động lại vào slot **{nxt_hhmm}** (~{mins} phút).",
            reply_markup=_kbd()
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

# ============== HEALTH MONITOR ==============
_last_fail_alert_ts = 0.0
_is_down = False

async def health_probe(context: ContextTypes.DEFAULT_TYPE):
    """Ping nhẹ để báo sự cố/phục hồi."""
    global _last_fail_alert_ts, _is_down
    chat_id = ALLOWED_USER_ID
    _, live, _ = await _probe_live()
    if live:
        if _is_down:
            _is_down = False
            await context.bot.send_message(
                chat_id, "✅ Hệ thống đã **phục hồi**. Tín hiệu sẽ gửi bình thường ở slot kế tiếp."
            )
        return

    now = time.time()
    if (now - _last_fail_alert_ts) >= FAIL_ALERT_COOLDOWN_SEC:
        _last_fail_alert_ts = now
        now_vn = datetime.now(VN_TZ)
        nxt_hhmm, mins = next_slot_info(now_vn)
        await context.bot.send_message(
            chat_id,
            f"🚨 **Cảnh báo kết nối**: không gọi được dữ liệu LIVE lúc {now_vn.strftime('%H:%M')}.\n"
            f"↪️ Slot kế tiếp: **{nxt_hhmm}** (~{mins} phút).",
        )
        _is_down = True

# ================== APP BUILDER ==================
def build_app() -> Application:
    app: Application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status_cmd))

    # Buttons (reply keyboard)
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(f"^{BTN_STATUS}"), status_cmd))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(f"^{BTN_TODAY}$"), macro_today))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(f"^{BTN_TOMORROW}$"), macro_tomorrow))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(f"^{BTN_WEEK}$"), macro_week))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(f"^{BTN_TEST}$"), pre_countdown))

    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(f"^{BTN_VND}$"),
                                   lambda u,c: _set_unit(u,c,"VND")))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(f"^{BTN_USD}$"),
                                   lambda u,c: _set_unit(u,c,"USD")))

    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(f"^{BTN_ON}$"),
                                   lambda u,c: _set_auto(u,c,True)))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(f"^{BTN_OFF}$"),
                                   lambda u,c: _set_auto(u,c,False)))

    # Scheduler
    j = app.job_queue
    j.run_daily(morning_brief, time=dt_time(6,0, tzinfo=VN_TZ))
    j.run_daily(macro_daily,   time=dt_time(7,0, tzinfo=VN_TZ))

    # Gửi batch & countdown mỗi slot
    for hhmm in SLOT_TIMES:
        h, m = map(int, hhmm.split(":"))
        mm = (m - 1) % 60
        hh = h if m > 0 else (h - 1)
        j.run_daily(pre_countdown,       time=dt_time(hh, mm, tzinfo=VN_TZ))
        j.run_daily(send_batch_scalping, time=dt_time(h,  m,  tzinfo=VN_TZ))

    # Health monitor
    j.run_repeating(health_probe, interval=HEALTH_POLL_SEC, first=10)

    return app
