# bots/handlers/top.py
import asyncio
import aiohttp
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

TOP_COINS_CACHE = []
UPDATE_INTERVAL = 300  # 5 phút

ONUS_API_URL = "https://api.goonus.io/v1/futures/market-summary"

async def fetch_top_coins():
    global TOP_COINS_CACHE
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(ONUS_API_URL, timeout=10) as resp:
                data = await resp.json()
                coins = data.get("data", [])
                # Sắp xếp theo volume 24h giảm dần
                coins.sort(key=lambda x: float(x.get("quoteVolume", 0)), reverse=True)
                # Chỉ lấy top 20
                TOP_COINS_CACHE = coins[:20]
    except Exception as e:
        print(f"[ERROR] Lấy dữ liệu Onus thất bại: {e}")

async def auto_update_top_coins():
    while True:
        await fetch_top_coins()
        await asyncio.sleep(UPDATE_INTERVAL)

async def top_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not TOP_COINS_CACHE:
        await update.message.reply_text("⚠️ Chưa có dữ liệu, vui lòng thử lại sau.")
        return

    msg = "🏆 **TOP 20 COIN VOLUME CAO (ONUS)**\n"
    for i, coin in enumerate(TOP_COINS_CACHE, start=1):
        symbol = coin["symbol"]
        vol = float(coin["quoteVolume"])
        change = float(coin.get("priceChangePercent", 0))
        msg += f"{i}. {symbol:<6} {vol/1_000_000_000:.1f}B  ({change:+.2f}%)\n"

    await update.message.reply_text(msg)

def register_top_handler(app):
    app.add_handler(CommandHandler("top", top_command))

def start_top_updater():
    asyncio.create_task(auto_update_top_coins())
