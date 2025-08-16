import aiohttp

TREND_KEYWORDS = {
    "AI": ["AI", "GPT", "NEURAL", "BOT"],
    "Layer2": ["L2", "ARBITRUM", "OPTIMISM", "ZKSYNC", "STARK"],
    "DeFi": ["DEX", "SWAP", "YIELD", "LENDING"],
    "GameFi": ["GAME", "ARENA", "PLAY", "METAVERSE"],
    "Meme": ["INU", "DOGE", "PEPE", "MEME"]
}

async def detect_trend(symbol: str, description: str = "") -> str:
    """
    Xác định coin thuộc trend nào dựa vào tên symbol + mô tả (nếu có).
    Trả về: "AI", "Layer2", "DeFi", "GameFi", "Meme", hoặc "Khác".
    """
    text = f"{symbol.upper()} {description.upper()}"
    for trend, keywords in TREND_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return trend
    return "Khác"
