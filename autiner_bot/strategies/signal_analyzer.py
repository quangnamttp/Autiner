def analyze_signal(coin: dict) -> dict:
    """
    Phân tích kỹ thuật cơ bản cho coin:
    - RSI
    - MA
    - Đề xuất LONG/SHORT
    - Xác định điểm vào/TP/SL
    """
    price = coin["lastPrice"]
    change_pct = coin["change_pct"]
    rsi = coin["rsi"]

    # Logic RSI
    if rsi > 70:
        rsi_signal = "QUÁ MUA (SELL)"
    elif rsi < 30:
        rsi_signal = "QUÁ BÁN (BUY)"
    else:
        rsi_signal = "TRUNG LẬP"

    # MA (dùng riseFallRate để demo MA)
    ma_signal = coin["ma_signal"]

    # Hướng lệnh
    side = "LONG" if change_pct > 0 else "SHORT"

    # Order type
    order_type = "MARKET" if abs(change_pct) > 2 else "LIMIT"

    # Tính TP/SL cơ bản
    tp_pct = 1.0 if side == "LONG" else -1.0
    sl_pct = -0.5 if side == "LONG" else 0.5

    tp_price = price * (1 + tp_pct / 100)
    sl_price = price * (1 + sl_pct / 100)

    return {
        "symbol": coin["symbol"],
        "side": side,
        "orderType": order_type,
        "entry": price,
        "tp": tp_price,
        "sl": sl_price,
        "strength": min(100, max(1, int(abs(change_pct) * 10))),
        "reason": f"RSI {rsi_signal} | MA {ma_signal} | Biến động {change_pct:.2f}%"
    }
