import json
import os

STATE_FILE = "bot_state.json"

def get_state():
    """Đọc trạng thái bot từ file."""
    if not os.path.exists(STATE_FILE):
        return {"is_on": True}
    with open(STATE_FILE, "r") as f:
        return json.load(f)

def save_state(state):
    """Lưu trạng thái bot vào file."""
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

def toggle_state():
    """Bật / tắt bot."""
    state = get_state()
    state["is_on"] = not state.get("is_on", True)
    save_state(state)
    return state
