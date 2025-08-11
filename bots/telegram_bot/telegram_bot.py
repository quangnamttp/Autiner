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
_current_unit = DEFAULT_UNIT  # "VND" or "USD"

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

# ----- helper cho /top: token trong khung, giá in đậm, bỏ funding -----
def _fmt_top_line(c: dict, unit: str) -> str:
    sym = c["symbol"].replace("_USDT", "")
    # giá
    if unit == "VND":
        price = f"{c['lastPriceVND']:,}₫".replace(",", ".")
    else:
        price = f"{c['lastPrice']:.4f} USDT".rstrip("0").rstrip(".")
    # Δ24h + mũi tên
    chg = float(c.get("change24h_pct", 0.0))
    arrow = "🟢" if chg > 0 else ("🔴" if chg < 0 else "⚪")
    chg_s = f"{arrow} {chg:+.2f}%"
    # dòng hiển thị đẹp (HTML)
    return f"<code>[ {sym} ]</code>  <b>{price}</b>   Δ24h = {chg_s}"

# ------------- commands -------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not guard(update): return
    await update.effective_chat.send_message(
        "AUTINER đã sẵn sàng.\n"
        "• /top — Top 30 theo đơn vị hiện tại\n"
        "• /status — Kiểm tra trạng thái dữ liệu",
        parse_mode=ParseMode.MARKDOWN
    )

# ----- /status: chỉ nguồn & trạng thái, không hiển thị VND -----
async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not guard(update): return
    # probe nhanh 1 mã để biết trạng thái dữ liệu
    _, live, _ = top_symbols(unit="USD", topn=1)
    text = (
        "📡 Trạng thái dữ liệu\n"
        "• Nguồn: MEXC Futures\n"
        f"• Trạng thái: {'LIVE ✅' if live else 'DOWN ❌'}\n"
    )
    await update.effective_chat.send_message(text)

# ----- /top: gọn, dễ đọc, bỏ funding & LIVE -----
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

# ------------- scheduled jobs -------------
async def morning_brief(context: ContextTypes.DEFAULT_TYPE):
    chat_id = ALLOWED_USER_ID
    now = datetime.now(VN_TZ)
    wd = weekday_vi(now)
    coins, live, rate = top_symbols(unit="USD", topn=30)
    if not live or not coins:
        await context.bot.send_message(chat_id, "⚠️ 06:00 không có dữ liệu LIVE để tạo bản tin sáng. Mình sẽ thử lại slot sau.")
        return

    long_votes = sum(1 for c in coins if c.get("change24h_pct",0)>=0 and c.get("fundingRate",0)>-0.02)
    long_pct = int(round(long_votes * 100 / max(1, len(coins))))
    short_pct = 100 - long_pct

    vols = sorted([c.get("volumeQuote",0) for c in coins])
    med = vols[len(vols)//2] if vols else 0
    filt = [c for c in coins if c.get("volumeQuote",0)>=med]
    filt.sort(key=lambda x: x.get("change24h_pct",0), reverse=True)
    gainers = filt[:5]

    lines = []
    lines.append("Chào buổi sáng nhé anh Trương ☀️")
    lines.append(f"Hôm nay: {wd}, {now.strftime('%H:%M %d/%m/%Y')}")
    lines.append("\nThị trường: nghiêng về " + ("LONG" if long_pct >= short_pct else "SHORT") + f" (Long {long_pct}% | Short {short_pct}%)")
    lines.append("• Tín hiệu tổng hợp: funding nhìn chung cân bằng, dòng tiền tập trung mid-cap.")

    if gainers:
        lines.append("\n5 đồng tăng trưởng nổi bật:")
        for i, c in enumerate(gainers, 1):
            sym = c["symbol"].replace("_USDT","")
            chg = c.get("change24h_pct", 0.0)
            vol = c.get("volumeQuote", 0.0)
            lines.append(f"{i}) {sym} • {chg:+.1f}% • VolQ ~ {vol:,.0f} USDT".replace(",", "."))
    else:
        lines.append("\nHôm nay biên độ thấp, ưu tiên quản trị rủi ro.")

    lines.append("\nGợi ý:")
    lines.append("• Giữ kỷ luật TP/SL, đừng FOMO nến mở phiên.")
    lines.append("• Chờ tín hiệu 30’ đầu tiên lúc 06:15 (mình sẽ đếm ngược trước 60s).")
    lines.append("Chúc anh một ngày trade thật thành công! 🍀")
    await context.bot.send_message(chat_id, "\n".join(lines))

async def macro_daily(context: ContextTypes.DEFAULT_TYPE):
    chat_id = ALLOWED_USER_ID
    await context.bot.send_message(
        chat_id,
        "📅 Lịch vĩ mô hôm nay (rút gọn):\n• Tạm thời chưa kết nối nguồn chi tiết.\n"
        "• Gợi ý: giữ vị thế nhẹ trước các khung giờ ra tin mạnh.",
    )

async def pre_countdown(context: ContextTypes.DEFAULT_TYPE):
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
            pass

async def send_batch_scalping(context: ContextTypes.DEFAULT_TYPE):
    chat_id = ALLOWED_USER_ID
    signals, highlights, live, rate = pick_scalping_signals(_current_unit, NUM_SCALPING)

    if (not live) or (not signals):
        now = datetime.now(VN_TZ)
        nxt_hhmm, mins = next_slot_info(now)
        await context.bot.send_message(
            chat_id,
            f"⚠️ Hệ thống đang gặp sự cố nên **slot {now.strftime('%H:%M')}** không có tín hiệu.\n"
            f"↪️ Dự kiến hoạt động lại vào slot **{nxt_hhmm}** (khoảng {mins} phút nữa)."
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

# Health monitor: cảnh báo gián đoạn & báo phục hồi
async def health_probe(context: ContextTypes.DEFAULT_TYPE):
    global _last_fail_alert_ts, _is_down
    chat_id = ALLOWED_USER_ID

    coins, live, rate = top_symbols(unit="USD", topn=1)
    if live and coins:
        if _is_down:
            _is_down = False
            await context.bot.send_message(chat_id, "✅ Hệ thống đã **phục hồi**. Tín hiệu sẽ gửi bình thường ở slot kế tiếp.")
        return

    now = time.time()
    if (now - _last_fail_alert_ts) >= FAIL_ALERT_COOLDOWN_SEC:
        _last_fail_alert_ts = now
        _is_down = True
        now_vn = datetime.now(VN_TZ)
        nxt_hhmm, mins = next_slot_info(now_vn)
        await context.bot.send_message(
            chat_id,
            f"🚨 **Cảnh báo kết nối**: không gọi được dữ liệu LIVE lúc {now_vn.strftime('%H:%M')}.\n"
            f"↪️ Slot kế tiếp: **{nxt_hhmm}** (~{mins} phút). Mình sẽ tự động thử lại."
        )

def build_app() -> Application:
    app: Application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("top", top_cmd))

    j = app.job_queue
    # 06:00 chào buổi sáng, 07:00 macro
    j.run_daily(morning_brief, time=dt_time(6,0, tzinfo=VN_TZ))
    j.run_daily(macro_daily,   time=dt_time(7,0, tzinfo=VN_TZ))

    # countdown và batch mỗi slot
    for hhmm in SLOT_TIMES:
        h, m = map(int, hhmm.split(":"))
        # countdown trước 60s
        mm = (m - 1) % 60
        hh = h if m > 0 else (h - 1)
        j.run_daily(pre_countdown,        time=dt_time(hh, mm, tzinfo=VN_TZ))
        j.run_daily(send_batch_scalping,  time=dt_time(h, m,  tzinfo=VN_TZ))

    # health monitor mỗi 60s
    j.run_repeating(health_probe, interval=HEALTH_POLL_SEC, first=10)

    return app
