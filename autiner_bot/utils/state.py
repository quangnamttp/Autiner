# autiner_bot/utils/state.py
"""
Trạng thái đơn giản cho bot.
- Lưu đơn vị hiển thị: "USDT" hoặc "VND"
- Có khoá để set thread-safe khi chạy Flask + PTB song song.
"""

from typing import Dict
import threading

_LOCK = threading.RLock()

# Trạng thái mặc định
_state: Dict[str, object] = {
    "currency_mode": "USDT",   # hoặc "VND"
}

def get_state() -> Dict[str, object]:
    """
    Trả về dict trạng thái hiện tại.
    Dùng read-only trong luồng khác nhau. Nếu cần sửa, dùng hàm setter.
    """
    return _state

def set_currency_mode(mode: str) -> None:
    """
    Đổi đơn vị hiển thị: "USDT" hoặc "VND".
    """
    mode = (mode or "").upper()
    if mode not in ("USDT", "VND"):
        mode = "USDT"
    with _LOCK:
        _state["currency_mode"] = mode

# (tuỳ chọn) reset trạng thái
def reset_state() -> None:
    with _LOCK:
        _state.clear()
        _state.update({"currency_mode": "USDT"})
