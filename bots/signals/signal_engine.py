import requests
from settings import settings
from bots.pricing.onus_format import display_price

def generate_signals(unit="VND", n=5):
    try:
        tickers = requests.get(settings.MEXC_TICKER_URL, timeout=10).json().get("data", [])
    except Exception:
        return []
    coins = []
    for t in tickers:
        vol = float(t.get("turnover", 0))
        if vol >= settings.VOL24H_FLOOR:
            coins.append({
                "token": t["symbol"],
                "side": "LONG" if float(t.get("riseFallRate", 0)) > 0 else "SHORT",
                "type": "Breakout",
                "orderType": "Market",
                "entry": display_price(1.23, unit),
                "tp": display_price(1.30, unit),
                "sl": display_price(1.10, unit),
                "strength": round(abs(float(t.get("riseFallRate", 0))) * 100, 2),
                "reason": "Khối lượng lớn + xu hướng rõ"
            })
    coins.sort(key=lambda x: x["strength"], reverse=True)
    return coins[:n]
