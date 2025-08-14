# autiner_bot/strategies/scalping.py
import random

def generate_scalping_signal(symbol: str):
    """
    Tạo tín hiệu scalping giả lập.
    Thực tế có thể dùng dữ liệu kỹ thuật từ MEXC để tính toán.
    """
    side = random.choice(["LONG", "SHORT"])
    entry = round(random.uniform(0.8, 1.2) * 100, 2)
    tp = entry * (1.01 if side == "LONG" else 0.99)
    sl = entry * (0.99 if side == "LONG" else 1.01)
    strength = random.randint(50, 90)
    reason = "Volume cao, xu hướng ngắn hạn thuận lợi"

    return {
        "symbol": symbol,
        "side": side,
        "type": "Scalping",
        "orderType": "Market",
        "entry": entry,
        "tp": tp,
        "sl": sl,
        "strength": strength,
        "reason": reason
    }
