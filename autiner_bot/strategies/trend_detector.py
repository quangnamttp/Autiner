# autiner_bot/strategies/trend_detector.py

"""
Module nhận diện trend & loại bỏ coin rác.
"""

# Mapping các trend phổ biến (tạm demo, có thể bổ sung thêm)
TREND_KEYWORDS = {
    "AI": ["AI", "FET", "AGIX", "RNDR", "ARKM"],
    "Layer2": ["ARB", "OP", "MATIC", "STRK", "ZKS"],
    "Meme": ["DOGE", "SHIB", "PEPE", "FLOKI"],
    "DeFi": ["UNI", "AAVE", "CAKE", "CRV"],
    "GameFi": ["AXS", "SAND", "MANA", "GALA"]
}

def detect_trend(symbol: str) -> str:
    """
    Kiểm tra coin thuộc trend nào dựa trên symbol.
    """
    for trend, keywords in TREND_KEYWORDS.items():
        for k in keywords:
            if k in symbol.upper():
                return trend
    return "Unknown"

def filter_coins(coins: list) -> list:
    """
    Lọc coin rác & chỉ giữ coin có trend mạnh.
    Input: danh sách coin [{symbol, lastPrice, change_pct, ...}]
    Output: danh sách coin đã gắn trend
    """
    filtered = []
    for c in coins:
        trend = detect_trend(c["symbol"])
        if trend != "Unknown":
            c["trend"] = trend
            filtered.append(c)
    return filtered
