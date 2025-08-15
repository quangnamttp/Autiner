# autiner_bot/scheduler.py
from telegram import Bot
from autiner_bot.settings import S
from autiner_bot.utils.state import get_state
from autiner_bot.utils.time_utils import get_vietnam_time
from autiner_bot.data_sources.mexc import get_top_moving_coins
from autiner_bot.data_sources.exchange import get_usdt_vnd_rate
from autiner_bot.jobs.daily_reports import job_morning_message, job_evening_summary
import asyncio
import traceback
import pytz
from datetime import time

bot = Bot(token=S.TELEGRAM_BOT_TOKEN)

# =============================
# Helpers: format giá
# =============================
def _trim_trailing_zeros(s: str) -> str:
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s

def format_price(value: float, currency: str = "USD", vnd_rate: float | None = None) -> str:
    """
    USD:
      - Giữ nguyên giá trị sàn, chỉ thêm dấu chấm tách nghìn khi >= 1
      - Không làm tròn vô nghĩa
    VND:
      - Luôn nhân vnd_rate; nếu không có vnd_rate => 'N/A VND' (tránh in sai)
      - >= 1000: phẩy tách nghìn, chấm là thập phân
      - 1 <= x < 1000: giữ số, chấm là thập phân (không ép định dạng)
      - < 1: bỏ '0.' và 0 đầu (vd 0.000585 -> 585 VND)
    """
    try:
        if currency == "VND":
            if not vnd_rate or vnd_rate <= 0:
                return "N/A VND"
            value = value * vnd_rate

            if value >= 1000:
                s = f"{value:,.12f}"             # nghìn = ',', thập phân='.'
                s = _trim_trailing_zeros(s)
                return s + " VND"
            elif value >= 1:
                s = f"{value:.12f}"
                s = _trim_trailing_zeros(s)
                return s + " VND"
            else:
                raw = f"{value:.12f}".rstrip('0').rstrip('.')
                # xóa '0.' và các số 0 đầu
                raw_no_zero = raw.replace("0.", "").lstrip("0")
                return (raw_no_zero or "0") + " VND"

        # USD
        if value >= 1:
            # :,.12f => nghìn=',' thập phân='.'; đổi nghìn thành '.' theo yêu cầu “thêm chấm cho dễ nhìn”
            s = f"{value:,.12f}"
            s = _trim_trailing_zeros(s)
            s = s.replace(",", ".")  # nghìn dùng chấm
            return s
        else:
            s = f"{value:.12f}"
            s = _trim_trailing_zeros(s)
            return s
    except Exception:
        return f"{value} {currency}"

# =============================
# Tạo tín hiệu
# =============================
def create_trade_signal(symbol: str, last_price: float, change_pct: float):
    direction = "LONG" if change_pct > 0 else "SHORT"
    order_type = "MARKET" if abs(change_pct) > 2 else "LIMIT"

    tp_pct = 0.5 if direction == "LONG" else -0.5
    sl_pct = -0.3 if direction == "LONG" else 0.3

    tp_price = last_price * (1 + tp_pct / 100.0)
    sl_price = last_price * (1 + sl_pct / 100.0)

    # Strength: tỉ lệ theo % biến động, tránh 0%
    strength = max(1, min(int(abs(change_pct) * 10), 100))

    return {
        "symbol": symbol,
        "side": direction,
        "orderType": order_type,
        "entry": last_price,
        "tp": tp_price,
        "sl": sl_price,
        "strength": strength,
        "reason": f"Biến động {change_pct:.2f}% trong 15 phút"
    }

# =============================
# Báo trước 1 phút
# =============================
async def job_trade_signals_notice():
    try:
        state = get_state()
        if not state["is_on"]:
            return
        await bot.send_message(
            chat_id=S.TELEGRAM_ALLOWED_USER_ID,
            text="⏳ 1 phút nữa sẽ có tín hiệu giao dịch!"
        )
    except Exception as e:
        print(f"[ERROR] job_trade_signals_notice: {e}")
        print(traceback.format_exc())

# =============================
# Gửi tín hiệu 30 phút/lần
# =============================
async def job_trade_signals():
    try:
        state = get_state()
        if not state["is_on"]:
            return

        # Lấy song song: ticker + tỷ giá (nếu cần)
        if state["currency_mode"] == "VND":
            moving_task = asyncio.create_task(get_top_moving_coins(limit=5))
            rate_task   = asyncio.create_task(get_usdt_vnd_rate())
            moving_coins, vnd_rate = await asyncio.gather(moving_task, rate_task)

            if not vnd_rate or vnd_rate <= 0:
                await bot.send_message(
                    chat_id=S.TELEGRAM_ALLOWED_USER_ID,
                    text="⚠️ Không lấy được tỷ giá USDT/VND ở vòng này nên tạm hoãn gửi tín hiệu VND."
                )
                return
            use_currency = "VND"
        else:
            moving_coins = await get_top_moving_coins(limit=5)
            vnd_rate = None
            use_currency = "USD"

        for c in moving_coins:
            # Tính % biến động tin cậy: ưu tiên change_pct; nếu ~0 thì dùng riseFallRate
            change_pct = 0.0
            try:
                change_pct = float(c.get("change_pct", 0.0))
            except:
                change_pct = 0.0
            if abs(change_pct) < 1e-9:
                try:
                    rf = float(c.get("riseFallRate", 0.0))
                    # Heuristic: nếu |rf| < 1 => coi là 0.x (tỷ lệ), chuyển sang %
                    change_pct = rf * 100.0 if abs(rf) < 1.0 else rf
                except:
                    pass

            last_price = float(c.get("lastPrice", 0.0))
            sig = create_trade_signal(c["symbol"], last_price, change_pct)

            entry_price = format_price(sig['entry'], use_currency, vnd_rate)
            tp_price    = format_price(sig['tp'],    use_currency, vnd_rate)
            sl_price    = format_price(sig['sl'],    use_currency, vnd_rate)

            symbol_display = sig['symbol'].replace("_USDT", f"/{use_currency}")
            side_icon = "🟩 LONG" if sig["side"] == "LONG" else "🟥 SHORT"
            highlight = "⭐ " if sig["strength"] >= 70 else ""

            msg = (
                f"{highlight}📈 {symbol_display} — {side_icon}\n\n"
                f"🔹 Kiểu vào lệnh: {sig['orderType']}\n"
                f"💰 Entry: {entry_price}\n"
                f"🎯 TP: {tp_price}\n"
                f"🛡️ SL: {sl_price}\n"
                f"📊 Độ mạnh: {sig['strength']}%\n"
                f"📌 Lý do: {sig['reason']}\n"
                f"🕒 Thời gian: {get_vietnam_time().strftime('%H:%M %d/%m/%Y')}"
            )
            await bot.send_message(chat_id=S.TELEGRAM_ALLOWED_USER_ID, text=msg)

    except Exception as e:
        print(f"[ERROR] job_trade_signals: {e}")
        print(traceback.format_exc())

# =============================
# Đăng ký job sáng & tối
# =============================
def register_daily_jobs(job_queue):
    tz = pytz.timezone("Asia/Ho_Chi_Minh")
    job_queue.run_daily(job_morning_message, time=time(hour=6, minute=0, tzinfo=tz), name="morning_report")
    job_queue.run_daily(job_evening_summary, time=time(hour=22, minute=0, tzinfo=tz), name="evening_report")
