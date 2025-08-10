import aiohttp
import asyncio
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

# Lưu cache dữ liệu để khi gọi /top thì trả ra nhanh
_top_cache = []
_lock = asyncio.Lock()

async def fetch_top_coins():
    """Lấy top 30 coin volume cao từ API Onus"""
    global _top_cache
    url = "https://api.onus.io/exchange/v1/market/24h-tickers"  # API công khai của Onus
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                data = await resp.json()
                coins = sorted(
                    data["data"], 
                    key=lambda x: float(x["quoteVolume"]), 
                    reverse=True
                )[:30]

                _top_cache = [
                    f"{i+1}. {c['symbol']}  Vol: {float(c['quoteVolume']):,.0f}  ({float(c['priceChangePercent']):+.2f}%)"
                    for i, c in enumerate(coins)
                ]
    except Exception as e:
        print("Lỗi fetch_top_coins:", e)

async def top_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Trả về danh sách top coin khi người dùng gọi /top"""
    if not _top_cache:
        await update.message.reply_text("⏳ Đang tải dữ liệu...")
        await fetch_top_coins()

    text = "🏆 TOP 30 COIN VOLUME CAO (ONUS)\n" + "\n".join(_top_cache)
    await update.message.reply_text(text)

def register_top_handler(app):
    app.add_handler(CommandHandler("top", top_command))

def start_top_updater():
    """Cập nhật dữ liệu coin mỗi 60 giây"""
    async def updater():
        while True:
            async with _lock:
                await fetch_top_coins()
            await asyncio.sleep(60)

    loop = asyncio.get_event_loop()
    loop.create_task(updater())
