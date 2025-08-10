from config.settings import ALLOWED_USER_ID

def is_allowed_user(user_id: int) -> bool:
    return user_id == ALLOWED_USER_ID
