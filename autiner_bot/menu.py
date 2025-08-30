from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import ContextTypes
from autiner_bot.utils import state
from autiner_bot.data_sources.binance import (
    get_usdt_vnd_rate,
    analyze_coin,
    get_all_futures,
)
from autiner_bot.utils.time_utils import get_vietnam_time

import re
import time

# ====== Cache ticker 24h để tránh 429 ======
_ALL_TICKERS_CACHE = {"ts": 0, "data": []}

async def _get_all_futures_cached(ttl: int = 10):
    """Cache danh sách futures trong ttl giây."""
    now = int(time.time())
    if now - _ALL_TICKERS_CACHE["ts"] <= ttl and _ALL_TICKERS_CACHE["data"]:
        return _ALL_TICKERS_CACHE["data"]
    data = await get_all_futures(ttl=ttl)  # đã có cache ở layer data_sources
    if data:
        _ALL_TICKERS_CACHE["ts"] = now
        _ALL_TICKERS_CACHE["data"] = data
    return data

# ===== Helpers =====
def _clean_symbol(text: str) -> str:
    """
    Chuẩn hoá input: " op / usdt " -> "OPUSDT"
    Nếu người dùng chỉ gõ "op" thì tự thêm "USDT".
    """
    t = (text or "").upper().strip()
    t = t.replace(" ", "").replace("-", "").replace("_", "")
    t = t.replace("\\", "/")
    # Normalize quote to USDT
    t = t.replace("USDC", "USDT").replace("USD", "USDT")
    t = re.sub(r"/+", "/", t)
    if "/" in t:
        base, _ = t.split("/", 1)
        t = base + "USDT"
    if not t.endswith("USDT"):
        t = t + "USDT"
    return t

def _prefer_symbol(query_base: str, futures_list: list) -> str | None:
    """
    Chọn symbol tốt nhất:
      1) Ưu tiên exact: BASEUSDT
      2) Nếu không có, tìm symbol bắt đầu bằng BASE, sort theo quoteVolume giảm dần.
    """
    exact = f"{query_base}USDT"
    have = [c.get("symbol") for c in futures_list]
    if exact in have:
        return exact

    candidates = []
    for c in futures_list:
        sym = c.get("symbol", "")
        if sym.startswith(query_base) and sym.endswith("USDT"):
            try:
                vol = float(c.get("quoteVolume") or c.get("volume") or 0.0)
            except Exception:
                vol = 0.0
            candidates.append((sym, vol))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[1], reverse=True)
    return candidates[0][0]

def _format_price(v: float, unit: str) -> str:
    return f"{v:,.0f}" if unit == "VND" else f"{v:,.2f}"

# ==== Tạo menu ====
def get_reply_menu():
    s = state.get_state()
    # Dùng nhãn USDT cho đúng bản chất
    currency_btn = "💵 USDT Mode" if s.get("currency_mode") == "VND" else "💴 VND Mode"
    keyboard = [["🔍 Trạng thái", currency_btn]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ==== /start ====
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s = state.get_state()
    unit = "VND" if s.get("currency_mode") == "VND" else "USDT"
    msg = (
        f"📡 Bot thủ công Binance Futures\n"
        f"• Đơn vị hiển thị: {unit}\n"
        f"👉 Gõ tên coin để phân tích (vd: op, btc, eth, 1000shib...)"
    )
    await update.message.reply_text(msg, reply_markup=get_reply_menu())

# ==== Xử lý input ====
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()

    # Đổi đơn vị USDT/VND
    tl = text.lower()
    if tl in ["💴 vnd mode", "💵 usdt mode"]:
        new_mode = "VND" if "vnd" in tl else "USDT"
        state.set_currency_mode(new_mode)
        await update.message.reply_text(f"💱 Đã chuyển sang {new_mode}", reply_markup=get_reply_menu())
        return

    # Trạng thái
    if tl == "🔍 trạng thái":
        s = state.get_state()
        unit = "VND" if s.get("currency_mode") == "VND" else "USDT"
        await update.message.reply_text(f"📡 Binance Futures\n• Đơn vị: {unit}", reply_markup=get_reply_menu())
        return

    # Lấy danh sách futures (có cache)
    all_coins = await _get_all_futures_cached(ttl=10)
    if not all_coins:
        await update.message.reply_text("⚠️ Không lấy được dữ liệu từ Binance Futures. Thử lại sau nhé.")
        return

    # Chuẩn hoá và chọn symbol
    cleaned = _clean_symbol(text)               # "OP" -> "OPUSDT"
    query_base = cleaned.replace("USDT", "")    # "OP"
    symbol = _prefer_symbol(query_base, all_coins)
    if not symbol:
        await update.message.reply_text(f"⚠️ Không tìm thấy {query_base} trên Binance Futures.")
        return

    # Tìm 24h record của symbol
    coin = None
    for c in all_coins:
        if c.get("symbol") == symbol:
            coin = c
            break
    if not coin:
        await update.message.reply_text(f"⚠️ Thiếu dữ liệu 24h cho {symbol}.")
        return

    # Giá hiện tại
    try:
        price = float(coin.get("lastPrice"))
    except Exception:
        await update.message.reply_text(f"⚠️ Không đọc được giá của {symbol}.")
        return

    # Đơn vị hiển thị & tỷ giá
    s = state.get_state()
    unit = "VND" if s.get("currency_mode") == "VND" else "USDT"
    vnd_rate = 0.0
    if unit == "VND":
        try:
            vnd_rate = await get_usdt_vnd_rate()
        except Exception:
            vnd_rate = 0.0

    # Phân tích
    trend = await analyze_coin(symbol)
    if not trend:
        await update.message.reply_text(f"⚠️ Không phân tích được {symbol}.")
        return

    side = trend.get("side", "LONG")
    strength = int(trend.get("strength", 50))
    reason = trend.get("reason", "—")

    # baseline TP/SL 1%
    tp = price * (1.01 if side == "LONG" else 0.99)
    sl = price * (0.99 if side == "LONG" else 1.01)

    entry_disp = price * vnd_rate if vnd_rate else price
    tp_disp = tp * vnd_rate if vnd_rate else tp
    sl_disp = sl * vnd_rate if vnd_rate else sl

    msg = (
        f"📈⭐ {symbol.replace('USDT','/'+unit)} — "
        f"{'🟢 LONG' if side=='LONG' else '🔴 SHORT'}\n\n"
        f"🔹 Kiểu vào lệnh: Market\n"
        f"💰 Entry: {_format_price(entry_disp, unit)} {unit}\n"
        f"🎯 TP: {_format_price(tp_disp, unit)} {unit}\n"
        f"🛡️ SL: {_format_price(sl_disp, unit)} {unit}\n"
        f"📊 Độ mạnh: {strength}%\n"
        f"📌 Lý do: {reason}\n"
        f"🕒 Thời gian: {get_vietnam_time().strftime('%H:%M %d/%m/%Y')}"
    )
    await update.message.reply_text(msg, reply_markup=get_reply_menu())
