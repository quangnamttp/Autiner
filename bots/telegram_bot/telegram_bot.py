import asyncio
import pytz
from datetime import datetime, time as dt_time
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application, ApplicationBuilder, CommandHandler, ContextTypes
)

from settings import (
    TELEGRAM_BOT_TOKEN, ALLOWED_USER_ID, TZ_NAME,
    SLOT_TIMES, NUM_SCALPING, DEFAULT_UNIT
)
from .mexc_api import top_symbols, pick_scalping_signals

VN_TZ = pytz.timezone(TZ_NAME)

# đơn vị hiển thị hiện tại (mặc định theo ENV)
_current_unit = DEFAULT_UNIT

def vn_now_str():
    now = datetime.now(VN_TZ)
    return now.strftime("%H:%M %d/%m/%Y")

def weekday_vi(dt: datetime) -> str:
    wd = dt.weekday()  # Mon=0..Sun=6
    names = ["Thứ Hai","Thứ Ba","Thứ Tư","Thứ Năm","Thứ Sáu","Thứ Bảy","Chủ Nhật"]
    return names[wd]

def guard(update: Update) -> bool:
    return not (ALLOWED_USER_ID and update.effective_user and update.effective_user.id != ALLOWED_USER_ID)

# ---------------- Commands ----------------
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
    coins, live, rate = top_symbols(unit=_current_unit, topn=5)
    status = "LIVE ✅" if live else "CACHE 🟡"
    rate_txt = f"{int(rate):,}₫/USDT".replace(",", ".")
    await update.effective_chat.send_message(f"Trạng thái dữ liệu: {status}\nTỷ giá: ~{rate_txt}")

async def top_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not guard(update): return
    coins, live, rate = top_symbols(unit=_current_unit, topn=30)
    if not coins:
        await update.effective_chat.send_message("⚠️ Hiện chưa lấy được dữ liệu. Thử lại sau nhé.")
        return
    head = f"📊 Top 30 Futures (MEXC) — Đơn vị: **{_current_unit}** — {'LIVE ✅' if live else 'CACHE 🟡'}"
    lines = [head]
    for i, c in enumerate(coins, 1):
        px = (f"{c['lastPriceVND']:,}₫".replace(",", ".") if _current_unit=="VND"
              else f"{c['lastPrice']:.4f} USDT".rstrip("0").rstrip("."))
        lines.append(f"{i:02d}. {c['symbol'].replace('_USDT','')} • {px} • Δ24h={c['change24h_pct']:.2f}% • f={c.get('fundingRate',0):+.3f}%")
    await update.effective_chat.send_message("\n".join(lines), parse_mode=ParseMode.MARKDOWN)

# --------------- Scheduler jobs ---------------
async def morning_brief(context: ContextTypes.DEFAULT_TYPE):
    chat_id = ALLOWED_USER_ID
    now = datetime.now(VN_TZ)
    wd = weekday_vi(now)
    coins, live, rate = top_symbols(unit="USD", topn=30)  # phân tích theo USD cho chuẩn Δ% & funding
    # nghiêng thị trường
    long_votes = 0
    for c in coins:
        if c.get("change24h_pct", 0) >= 0 and c.get("fundingRate", 0) > -0.02:
            long_votes += 1
    long_pct = int(round(long_votes * 100 / max(1, len(coins))))
    short_pct = 100 - long_pct

    # chọn 5 đồng tăng nổi bật (volume >= median)
    vols = sorted([c.get("volumeQuote", 0) for c in coins])
    med = vols[len(vols)//2] if vols else 0
    filt = [c for c in coins if c.get("volumeQuote",0) >= med]
    filt.sort(key=lambda x: x.get("change24h_pct", 0), reverse=True)
    gainers = filt[:5]

    lines = []
    lines.append("Chào buổi sáng nhé anh Trương ☀️")
    lines.append(f"Hôm nay: {wd}, {now.strftime('%H:%M %d/%m/%Y')} • Tỷ giá: ~{int(rate):,}₫/USDT".replace(",", "."))
    tilt = "LONG" if long_pct >= short_pct else "SHORT"
    lines.append(f"\nThị trường: nghiêng về {tilt} (Long {long_pct}% | Short {short_pct}%)")
    lines.append("• Tín hiệu tổng hợp: funding nhìn chung cân bằng, dòng tiền tập trung mid-cap.")

    if gainers:
        lines.append("\n5 đồng tăng trưởng nổi bật:")
        for i, c in enumerate(gainers, 1):
            sym = c["symbol"].replace("_USDT","")
            chg = c.get("change24h_pct", 0.0)
            vol = c.get("volumeQuote", 0.0)
            fr  = c.get("fundingRate", 0.0)
            lines.append(f"{i}) {sym} • {chg:+.1f}% • VolQ ~ {vol:,.0f} USDT • f={fr:+.3f}%".replace(",", "."))
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
        "📅 Lịch vĩ mô hôm nay (rút gọn):\n• Tạm thời chưa kết nối nguồn dữ liệu chi tiết.\n"
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
    if not signals:
        await context.bot.send_message(chat_id, "⚠️ Không lấy được dữ liệu. Mình sẽ thử lại ở slot kế tiếp.")
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

# --------------- Build app ---------------
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
        # đếm ngược 60s trước slot
        mm = (m - 1) % 60
        hh = h if m > 0 else (h - 1)
        j.run_daily(pre_countdown,        time=dt_time(hh, mm, tzinfo=VN_TZ))
        j.run_daily(send_batch_scalping,  time=dt_time(h, m,  tzinfo=VN_TZ))

    return app
