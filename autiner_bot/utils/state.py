# autiner_bot/utils/state.py
import os
import json

STATE_FILE = "bot_state.json"

# ==== Load trạng thái ====
def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {"is_on": True}

# ==== Lưu trạng thái ====
def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

# ==== Lấy trạng thái ====
def get_state():
    return load_state()

# ==== Set trạng thái (tương thích menu.py) ====
def set_state(new_state: dict):
    save_state(new_state)

# ==== Bật/Tắt ====
def set_on_off(status: bool):
    state = load_state()
    state["is_on"] = status
    save_state(state)
