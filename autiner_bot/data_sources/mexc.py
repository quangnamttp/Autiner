import aiohttp
import traceback

MEXC_BASE_URL = "https://contract.mexc.com"

# =============================
# Lấy dữ liệu ticker Futures (Top 20, giá > 0.01)
# =============================
async def get_top_futures(limit: int = 20):
    try:
        url = f"{MEXC_BASE_URL}/api/v1/contract/ticker"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                data = await resp.json()
                if not data or "data" not in data:
                    return []
                tickers = data["data"]

                coins = []
                for t in tickers:
                    symbol = t.get("symbol", "")
                    if not symbol.endswith("_USDT"):
                        continue
                    last_price = float(t["lastPrice"])
                    if last_price <= 0.01:   # ✅ chỉ lấy coin giá > 0.01
                        continue
                    coins.append({
                        "symbol": symbol,
                        "lastPrice": last_price,
                        "volume": float(t.get("amount24", 0)),
                        "change_pct": float(t.get("riseFallRate", 0)) * 100
                    })

                # Sắp xếp theo volume giảm dần, lấy top N
                coins.sort(key=lambda x: x["volume"], reverse=True)
                return coins[:limit]
    except Exception as e:
        print(f"[ERROR] get_top_futures: {e}")
        print(traceback.format_exc())
        return []


# =============================
# Lấy tỷ giá USDT/VND
# =============================
async def get_usdt_vnd_rate() -> float:
    url = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"
    payload = {
        "asset": "USDT",
        "fiat": "VND",
        "merchantCheck": False,
        "page": 1,
        "rows": 10,
        "tradeType": "SELL"
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=10) as resp:
                data = await resp.json()
                advs = data.get("data", [])
                if not advs:
                    return 0
                prices = [float(ad["adv"]["price"]) for ad in advs[:5] if "adv" in ad]
                return sum(prices) / len(prices) if prices else 0
    except Exception:
        return 0


# =============================
# Phân tích xu hướng coin (dựa trên % thay đổi 24h)
# =============================
async def analyze_coin_trend(symbol: str, last_price: float, change_pct: float):
    try:
        side = "LONG" if change_pct >= 0 else "SHORT"
        strength = min(100, max(50, abs(change_pct) * 10))  # scale strength 50–100
        reason = f"Biến động 24h: {change_pct:.2f}% → Xu hướng {side}"

        return {
            "side": side,
            "strength": round(strength, 1),
            "reason": reason,
            "lastPrice": last_price,
            "is_weak": strength < 60
        }
    except Exception as e:
        print(f"[ERROR] analyze_coin_trend({symbol}): {e}")
        return {
            "side": "LONG",
            "strength": 50,
            "reason": "Error fallback",
            "lastPrice": last_price,
            "is_weak": True
        }


# =============================
# Phân tích xu hướng thị trường (Daily)
# =============================
async def analyze_market_trend():
    try:
        coins = await get_top_futures(limit=20)  # ✅ lấy top 20
        if not coins:
            return {"long": 50, "short": 50, "trend": "❓ Không xác định", "top": []}

        long_vol = sum(c["volume"] for c in coins if c["change_pct"] > 0)
        short_vol = sum(c["volume"] for c in coins if c["change_pct"] < 0)
        total_vol = long_vol + short_vol

        if total_vol == 0:
            return {"long": 50, "short": 50, "trend": "⚖️ Sideway", "top": []}

        long_pct = round(long_vol / total_vol * 100, 1)
        short_pct = round(short_vol / total_vol * 100, 1)

        if long_pct > short_pct + 5:
            trend = "📈 Xu hướng TĂNG (phe LONG chiếm ưu thế)"
        elif short_pct > long_pct + 5:
            trend = "📉 Xu hướng GIẢM (phe SHORT chiếm ưu thế)"
        else:
            trend = "⚖️ Thị trường sideway"

        top = sorted(coins, key=lambda x: abs(x["change_pct"]), reverse=True)[:5]

        return {"long": long_pct, "short": short_pct, "trend": trend, "top": top}
    except Exception:
        return {"long": 50, "short": 50, "trend": "❓ Không xác định", "top": []}
