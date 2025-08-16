import json
import os

STATE_FILE = "/tmp/bot_state.json"

DEFAULT_STATE = {
    "is_on": True,
    "currency_mode": "VND"  # hoặc "USD"
}

def load_state():
    if not os.path.exists(STATE_FILE):
        save_state(DEFAULT_STATE)
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def toggle_on_off():
    state = load_state()
    state["is_on"] = not state["is_on"]
    save_state(state)
    return state["is_on"]

def set_on_off(status: bool):
    """Bật hoặc tắt bot"""
    state = load_state()
    state["is_on"] = status
    save_state(state)

def set_currency_mode(mode: str):
    if mode not in ("USD", "VND"):
        return
    state = load_state()
    state["currency_mode"] = mode
    save_state(state)

def get_state():
    return load_state()
