import aiosqlite
from src.database import get_or_create_session, get_session_messages, add_message

class ContextManager:
    def __init__(self, db_path: str):
        self.db_path = db_path

    async def get_context(self, user_id: int, limit: int = 20) -> list:
        """Returns list of dicts: [{"role": str, "content": str}, ...]"""
        async with aiosqlite.connect(self.db_path) as db:
            session_id = await get_or_create_session(db, user_id)
            rows = await get_session_messages(db, session_id, limit)

        # rows is list of tuples [(role, content), ...]
        messages = []
        for role, content in rows:
            if content and str(content).strip():
                messages.append({"role": role, "content": str(content).strip()})
        return messages

    async def add_to_context(self, user_id: int, role: str, content: str):
        async with aiosqlite.connect(self.db_path) as db:
            session_id = await get_or_create_session(db, user_id)
            await add_message(db, session_id, role, content)
