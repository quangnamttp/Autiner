from typing import List, Dict
from common.time_utils import fmt_vn
from adapters.exchanges.onus_futures import batch_signals, top_volume_symbols

def format_signal(sig: Dict) -> str:
    star = "\n⭐ Tín hiệu nổi bật" if sig["strength"] >= 70 else ""
    return (
        f"📈 {sig['symbol']} – {sig['side']}\n"
        f"🔹 {sig['type']} | {sig['orderType']}\n"
        f"💰 Entry: {sig['entry']:,} VNĐ\n"
        f"🎯 TP: {sig['tp']:,} VNĐ\n"
        f"🛡️ SL: {sig['sl']:,} VNĐ\n"
        f"📊 Độ mạnh: {sig['strength']}%\n"
        f"📌 Lý do: {sig['reason']}\n"
        f"🕒 {fmt_vn(sig['ts'])}"
        f"{star}"
    )

def get_batch_text() -> str:
    symbols = top_volume_symbols(limit=10)
    sigs: List[Dict] = batch_signals(symbols)
    blocks = [format_signal(s) for s in sigs]
    return "\n\n---\n\n".join(blocks)
