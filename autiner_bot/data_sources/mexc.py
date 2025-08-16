import aiohttp
import statistics

# =============================
# Hàm tiện ích gọi API
# =============================
async def fetch_json(url: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=10) as resp:
            return await resp.json()

# =============================
# Lấy tất cả tickers futures từ MEXC
# =============================
async def get_all_tickers():
    try:
        data = await fetch_json("https://contract.mexc.com/api/v1/contract/ticker")
        return data.get("data", [])
    except Exception as e:
        print(f"[ERROR] get_all_tickers: {e}")
        return []

# =============================
# Phân tích chuyên sâu & chọn tín hiệu
# =============================
async def get_top_signals(limit: int = 5):
    tickers = await get_all_tickers()
    futures = [t for t in tickers if t.get("symbol", "").endswith("_USDT")]

    signals = []
    for f in futures:
        try:
            symbol = f["symbol"]
            last_price = float(f.get("lastPrice", 0))
            change_pct = float(f.get("riseFallRate", 0)) * 100

            # Giả lập dữ liệu close price cho RSI & MA
            closes = [last_price * (1 + (change_pct/100) * (i/15)) for i in range(15)]

            # RSI
            gains = [max(closes[i] - closes[i-1], 0) for i in range(1, len(closes))]
            losses = [max(closes[i-1] - closes[i], 0) for i in range(1, len(closes))]
            avg_gain = statistics.mean(gains) if gains else 0.1
            avg_loss = statistics.mean(losses) if losses else 0.1
            rs = avg_gain / avg_loss if avg_loss != 0 else 100
            rsi = 100 - (100 / (1 + rs))

            # MA (trung bình động)
            ma = statistics.mean(closes)
            ma_signal = "BUY" if last_price > ma else "SELL"

            signals.append({
                "symbol": symbol,
                "lastPrice": last_price,
                "change_pct": change_pct,
                "rsi": round(rsi, 2),
                "ma_signal": ma_signal,
            })
        except Exception as e:
            print(f"[WARN] signal error {f}: {e}")
            continue

    # Sắp xếp theo độ biến động mạnh nhất
    signals = sorted(signals, key=lambda x: abs(x["change_pct"]), reverse=True)
    return signals[:limit]

# =============================
# Sentiment thị trường BTC
# =============================
async def get_market_sentiment():
    try:
        url = "https://contract.mexc.com/api/v1/contract/long_short_account_ratio?symbol=BTC_USDT&period=5m"
        data = await fetch_json(url)
        if data.get("success") and data.get("data"):
            latest = data["data"][-1]
            return {
                "long": float(latest.get("longAccount", 0)),
                "short": float(latest.get("shortAccount", 0))
            }
    except Exception as e:
        print(f"[ERROR] get_market_sentiment: {e}")
    return {"long": 0.0, "short": 0.0}

# =============================
# Funding & volume BTC
# =============================
async def get_market_funding_volume():
    try:
        funding_url = "https://contract.mexc.com/api/v1/contract/funding_rate?symbol=BTC_USDT"
        funding_data = await fetch_json(funding_url)
        funding_rate = funding_data.get("data", {}).get("fundingRate", "0%")

        tickers = await get_all_tickers()
        volume = "N/A"
        trend = "N/A"
        for item in tickers:
            if item.get("symbol") == "BTC_USDT":
                volume = f"{float(item.get('volume', 0)) / 1_000_000:.2f}M USDT"
                change_pct = float(item.get("riseFallRate", 0))
                trend = "📈 Tăng" if change_pct > 0 else "📉 Giảm" if change_pct < 0 else "➖ Đi ngang"
                break

        return {
            "funding": funding_rate,
            "volume": volume,
            "trend": trend
        }
    except Exception as e:
        print(f"[ERROR] get_market_funding_volume: {e}")
    return {"funding": "0%", "volume": "N/A", "trend": "N/A"}
