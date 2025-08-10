from typing import List, Dict
from common.time_utils import fmt_vn
from adapters.exchanges.onus_futures import batch_signals, top_volume_symbols

def format_signal(sig: Dict) -> str:
    side_icon = "🟩" if sig["side"] == "LONG" else "🟥"
    type_icon = "🟢" if sig["type"].lower() == "scalping" else "🔵"

    if sig["strength"] >= 70:
        strength_label = "Mạnh"
    elif sig["strength"] >= 50:
        strength_label = "Tiêu chuẩn"
    else:
        strength_label = "Tham khảo"

    return (
        f"📈 {sig['symbol']}(VND) — {side_icon} {sig['side']}\n\n"
        f"{type_icon} Loại lệnh: {sig['type']}\n"
        f"🔹 Kiểu vào lệnh: {sig['orderType']}\n"
        f"💰 Entry: {sig['entry']:,}\n"
        f"🎯 TP: {sig['tp']:,}\n"
        f"🛡️ SL: {sig['sl']:,}\n"
        f"📊 Độ mạnh: {sig['strength']}% ({strength_label})\n"
        f"📌 Lý do: Funding={sig.get('funding','-')}, "
        f"Vol5m={sig.get('vol_mult','-')}, "
        f"RSI={sig.get('rsi','-')}, "
        f"EMA9={sig.get('ema9','-')}, "
        f"EMA21={sig.get('ema21','-')}\n"
        f"🕒 Thời gian: {fmt_vn(sig['ts'])}"
    )

def get_batch_messages() -> List[str]:
    """Trả về danh sách message đã format (5 tín hiệu: 3 Scalping + 2 Swing)."""
    symbols = top_volume_symbols(limit=10)
    sigs: List[Dict] = batch_signals(symbols)
    return [format_signal(s) for s in sigs]
