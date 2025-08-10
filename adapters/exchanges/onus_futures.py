from typing import List, Dict
from common.time_utils import now_vn

def top_volume_symbols(limit=10) -> List[str]:
    # TODO(V2): lấy từ ONUS Futures
    return ["BTC","ETH","SOL","BNB","XRP","ADA","DOGE","OP","ARB","TON"][:limit]

def funding_rate(symbol: str) -> float:
    # TODO(V2): ONUS Futures funding rate
    return 0.01

def latest_price_vnd(symbol: str) -> int:
    # TODO(V2): giá VND từ ONUS Futures
    seed = sum(map(ord, symbol)) % 9
    base = {
        "BTC": 1_690_000_000, "ETH": 59_500_000, "SOL": 3_480_000,
        "BNB": 15_000_000, "XRP": 13_000
    }.get(symbol, 1_000_000 + seed*1000)
    return base

def batch_signals(symbols: List[str]) -> List[Dict]:
    # Tạo 3 Scalping + 2 Swing mẫu, VND-only
    out = []
    pairs = [("LONG","Scalping"),("SHORT","Scalping"),("LONG","Scalping"),
             ("SHORT","Swing"),("LONG","Swing")]
    for sym, (side, typ) in zip(symbols[:5], pairs):
        p = latest_price_vnd(sym)
        sl = int(p * (0.99 if side=="LONG" else 1.01))
        tp = int(p * (1.02 if side=="LONG" else 0.98))
        strength = 85 if sym in ("BTC","BNB") else 62
        out.append({
            "symbol": sym, "side": side, "type": typ, "orderType": "Market",
            "entry": p, "tp": tp, "sl": sl, "strength": strength,
            "reason": "Volume xác nhận + cấu trúc giá thuận chiều",
            "ts": now_vn()
        })
    return out
