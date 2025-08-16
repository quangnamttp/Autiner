import json
import os

# Lưu tại root của project (an toàn hơn khi deploy)
STATE_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "bot_state.json"))

DEFAULT_STATE = {
    "is_on": True,
    "currency_mode": "VND"  # hoặc "USD"
}

def ensure_state_keys(state: dict) -> dict:
    """Đảm bảo state luôn có đủ key mặc định"""
    new_state = DEFAULT_STATE.copy()
    new_state.update(state)
    return new_state

def load_state():
    try:
        if not os.path.exists(STATE_FILE):
            save_state(DEFAULT_STATE)
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)
            return ensure_state_keys(state)
    except Exception as e:
        print(f"[ERROR] load_state: {e} -> reset mặc định")
        save_state(DEFAULT_STATE)
        return DEFAULT_STATE

def save_state(state: dict):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(ensure_state_keys(state), f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[ERROR] save_state: {e}")

def toggle_on_off():
    state = load_state()
    state["is_on"] = not state["is_on"]
    save_state(state)
    return state["is_on"]

def set_on_off(status: bool):
    """Bật hoặc tắt bot"""
    state = load_state()
    state["is_on"] = bool(status)
    save_state(state)

def set_currency_mode(mode: str):
    if mode not in ("USD", "VND"):
        print(f"[WARN] set_currency_mode: mode không hợp lệ ({mode})")
        return
    state = load_state()
    state["currency_mode"] = mode
    save_state(state)

def get_state() -> dict:
    return load_state()
