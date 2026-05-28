from src.config import get_allowed_users

async def check_user_allowed(user_id: int) -> bool:
    allowed = get_allowed_users()
    if not allowed:
        return True
    return user_id in allowed
