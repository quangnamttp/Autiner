import random
from autiner_bot.data_sources.mexc import get_usdt_pairs
from autiner_bot.data_sources.trend_detector import get_coin_trend

# =============================
# Giả lập phân tích kỹ thuật
# =============================
def calc_rsi(change_pct: float) -> float:
    return 50 + (change_pct * 2)  # demo RSI

def ma_signal(change_pct: float) -> str:
    return "BUY" if change_pct > 0 else "SELL"

# =============================
# Tạo tín hiệu
# =============================
async def generate_signals(limit: int = 5):
    """
    Lấy coin từ MEXC → check trend Coingecko → phân tích → tạo tín hiệu
    """
    coins = await get_usdt_pairs()
    signals = []

    for coin in coins[:limit * 2]:  # lấy rộng hơn để lọc
        trends = await get_coin_trend(coin["symbol"].lower())
        rsi = calc_rsi(coin["change_pct"])
        ma = ma_signal(coin["change_pct"])

        if not trends:
            continue  # coin không rõ trend → bỏ qua

        signals.append({
            "symbol": coin["symbol"],
            "price": coin["lastPrice"],
            "change_pct": coin["change_pct"],
            "volume": coin["volume"],
            "trend": trends,
            "rsi": round(rsi, 2),
            "ma_signal": ma,
            "reason": f"{coin['symbol']} thuộc trend {', '.join(trends)}, RSI={round(rsi,2)}, MA={ma}, biến động {coin['change_pct']}%"
        })

    # Sắp xếp ưu tiên coin có biến động mạnh + trend rõ
    sorted_signals = sorted(signals, key=lambda x: abs(x["change_pct"]), reverse=True)
    return sorted_signals[:limit]
