# autiner_bot/strategies/swing.py
import random

def generate_swing_signal(symbol: str):
    """
    Tạo tín hiệu swing giả lập.
    Có thể mở rộng dùng phân tích khung H4/D1.
    """
    side = random.choice(["LONG", "SHORT"])
    entry = round(random.uniform(0.8, 1.2) * 100, 2)
    tp = entry * (1.03 if side == "LONG" else 0.97)
    sl = entry * (0.98 if side == "LONG" else 1.02)
    strength = random.randint(50, 90)
    reason = "Xu hướng trung hạn mạnh, hỗ trợ/kháng cự rõ"

    return {
        "symbol": symbol,
        "side": side,
        "type": "Swing",
        "orderType": "Limit",
        "entry": entry,
        "tp": tp,
        "sl": sl,
        "strength": strength,
        "reason": reason
    }
