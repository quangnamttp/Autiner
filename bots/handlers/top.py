# bots/handlers/top.py
import asyncio
import aiohttp
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

UPDATE_INTERVAL = 300  # 5 phút
TOP_LIMIT = 20

# cache dùng chung
_TOP = []
_FETCHING = False

# Một số endpoint của ONUS (tùy lúc site đổi, ta thử lần lượt)
ONUS_TICKERS_URLS = [
    # (ưu tiên) gateway chính
    "https://api-gateway.onus.io/futures/api/v1/market/tickers",
    # fallback khác (nếu có)
    "https://api.onus.io/futures/api/v1/market/tickers",
]

def _fmt_billion(v: float) -> str:
    try:
        v = float(v)
    except Exception:
        return "-"
    if v >= 1_000_000_000:
        return f"{v/1_000_000_000:.1f}B"
    if v >= 1_000_000:
        return f"{v/1_000_000:.1f}M"
    return f"{v:,.0f}"

async def _fetch_once(session: aiohttp.ClientSession, url: str):
    async with session.get(url, timeout=10) as r:
        j = await r.json()
        data = j.get("data") or j  # một số API trả trực tiếp list
        if not isinstance(data, list):
            return []
        out = []
        for it in data:
            # Chuẩn hóa field (vì mỗi endpoint tên hơi khác)
            sym = it.get("symbol") or it.get("pair") or it.get("token") or "-"
            price = it.get("lastPrice") or it.get("priceVnd") or it.get("lastPriceVnd") or it.get("last")
            change = it.get("priceChangePercent") or it.get("changePercent") or it.get("percentChange")
            vol = it.get("quoteVolume") or it.get("volumeValueVnd") or it.get("quoteVolumeVnd") or it.get("volume")
            try:
                price = float(price) if price is not None else None
            except Exception:
                price = None
            try:
                change = float(change) if change is not None else 0.0
            except Exception:
                change = 0.0
            try:
                vol = float(vol) if vol is not None else 0.0
            except Exception:
                vol = 0.0
            out.append({"symbol": sym, "price": price, "change": change, "vol": vol})
        # sắp xếp theo vol giảm dần
        out.sort(key=lambda x: x["vol"], reverse=True)
        return out[:TOP_LIMIT]

async def refresh_top():
    global _TOP, _FETCHING
    if _FETCHING:
        return
    _FETCHING = True
    try:
        async with aiohttp.ClientSession() as s:
            for url in ONUS_TICKERS_URLS:
                try:
                    top = await _fetch_once(s, url)
                    if top:
                        _TOP = top
                        break
                except Exception:
                    continue
    finally:
        _FETCHING = False

async def updater_loop():
    while True:
        await refresh_top()
        await asyncio.sleep(UPDATE_INTERVAL)

async def cmd_top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # lần đầu chưa có cache → refresh nhanh
    if not _TOP:
        await update.message.reply_text("⏳ Đang tải dữ liệu Onus…")
        await refresh_top()
        if not _TOP:
            await update.message.reply_text("⚠️ Hiện chưa lấy được dữ liệu. Thử lại sau nhé.")
            return

    lines = ["🏆 TOP 20 COIN VOLUME CAO (ONUS)\n"]
    for i, c in enumerate(_TOP, 1):
        price = f"{int(c['price']):,}₫" if c["price"] else "-"
        vol = _fmt_billion(c["vol"])
        arrow = "🟢" if c["change"] >= 0 else "🔴"
        lines.append(f"{i:>2}. {c['symbol']:<8} {price:<12} Vol:{vol:<6} {arrow} {c['change']:+.2f}%")
    await update.message.reply_text("\n".join(lines))

def register_top_handler(app):
    app.add_handler(CommandHandler("top", cmd_top))

def start_top_updater():
    asyncio.get_event_loop().create_task(updater_loop())
