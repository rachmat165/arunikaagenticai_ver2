import aiosqlite

async def init_db(db_path: str):
    async with aiosqlite.connect(db_path) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA synchronous=NORMAL")

        await db.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                platform TEXT DEFAULT 'telegram',
                model_provider TEXT DEFAULT 'anthropic',
                model_name TEXT DEFAULT 'claude-sonnet-4-6',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                cost_usd REAL DEFAULT 0.0
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                tool_calls TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER PRIMARY KEY,
                model_provider TEXT DEFAULT 'anthropic',
                model_name TEXT DEFAULT 'claude-sonnet-4-6',
                temperature REAL DEFAULT 0.7,
                max_tokens INTEGER DEFAULT 4096,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS usage_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                provider TEXT NOT NULL,
                model_name TEXT NOT NULL,
                input_tokens INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                cost_usd REAL DEFAULT 0.0,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS cron_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                task TEXT NOT NULL,
                schedule TEXT NOT NULL,
                next_run TIMESTAMP,
                last_run TIMESTAMP,
                last_result TEXT,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS generated_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                doc_type TEXT NOT NULL,
                title TEXT,
                file_path TEXT NOT NULL,
                file_size_bytes INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                generated_at_seconds REAL
            )
        """)

        await db.execute("CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_usage_user_id ON usage_log(user_id)")
        await db.commit()


async def get_or_create_session(db: aiosqlite.Connection, user_id: int) -> int:
    cursor = await db.execute("SELECT id FROM sessions WHERE user_id = ?", (user_id,))
    row = await cursor.fetchone()
    if row:
        return row[0]
    cursor = await db.execute("INSERT INTO sessions (user_id) VALUES (?)", (user_id,))
    await db.commit()
    return cursor.lastrowid


async def add_message(db: aiosqlite.Connection, session_id: int, role: str, content: str, tool_calls: str = None):
    await db.execute(
        "INSERT INTO messages (session_id, role, content, tool_calls) VALUES (?, ?, ?, ?)",
        (session_id, role, content, tool_calls)
    )
    await db.commit()


async def get_session_messages(db: aiosqlite.Connection, session_id: int, limit: int = 20) -> list:
    cursor = await db.execute(
        "SELECT role, content FROM messages WHERE session_id = ? ORDER BY timestamp DESC LIMIT ?",
        (session_id, limit)
    )
    rows = await cursor.fetchall()
    return list(reversed(rows))


async def set_user_model(db: aiosqlite.Connection, user_id: int, provider: str, model_name: str):
    await db.execute(
        """INSERT INTO user_settings (user_id, model_provider, model_name, updated_at)
           VALUES (?, ?, ?, CURRENT_TIMESTAMP)
           ON CONFLICT(user_id) DO UPDATE SET
               model_provider = excluded.model_provider,
               model_name = excluded.model_name,
               updated_at = CURRENT_TIMESTAMP""",
        (user_id, provider, model_name)
    )
    await db.commit()


async def get_user_model(db: aiosqlite.Connection, user_id: int) -> tuple:
    cursor = await db.execute(
        "SELECT model_provider, model_name FROM user_settings WHERE user_id = ?",
        (user_id,)
    )
    row = await cursor.fetchone()
    if row:
        return row
    return ("anthropic", "claude-sonnet-4-6")


async def log_usage(db: aiosqlite.Connection, user_id: int, provider: str, model_name: str,
                    input_tokens: int, output_tokens: int, cost_usd: float):
    await db.execute(
        """INSERT INTO usage_log (user_id, provider, model_name, input_tokens, output_tokens, cost_usd)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (user_id, provider, model_name, input_tokens, output_tokens, cost_usd)
    )
    await db.commit()


async def get_user_usage(db: aiosqlite.Connection, user_id: int) -> dict:
    cursor = await db.execute(
        """SELECT
               SUM(input_tokens) as total_input,
               SUM(output_tokens) as total_output,
               SUM(cost_usd) as total_cost,
               COUNT(*) as total_calls,
               MAX(timestamp) as last_used
           FROM usage_log WHERE user_id = ?""",
        (user_id,)
    )
    row = await cursor.fetchone()
    if not row or row[0] is None:
        return {"total_input": 0, "total_output": 0, "total_cost": 0.0, "total_calls": 0, "last_used": None}
    return {
        "total_input": row[0] or 0,
        "total_output": row[1] or 0,
        "total_cost": row[2] or 0.0,
        "total_calls": row[3] or 0,
        "last_used": row[4],
    }


async def count_session_messages(db: aiosqlite.Connection, session_id: int) -> int:
    cursor = await db.execute(
        "SELECT COUNT(*) FROM messages WHERE session_id = ?", (session_id,)
    )
    row = await cursor.fetchone()
    return row[0] if row else 0


async def get_all_session_messages(db: aiosqlite.Connection, session_id: int) -> list:
    """Get ALL messages (no limit) for compression."""
    cursor = await db.execute(
        "SELECT role, content FROM messages WHERE session_id = ? ORDER BY timestamp ASC",
        (session_id,)
    )
    return await cursor.fetchall()


async def replace_messages_with_summary(db: aiosqlite.Connection, session_id: int, summary: str):
    """Delete all messages and insert a single summary message."""
    await db.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
    await db.execute(
        "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
        (session_id, "user", f"[RINGKASAN PERCAKAPAN SEBELUMNYA]\n{summary}")
    )
    await db.execute(
        "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
        (session_id, "assistant", "Baik, saya sudah memahami ringkasan percakapan kita sebelumnya. Silakan lanjutkan.")
    )
    await db.commit()


async def get_usage_by_model(db: aiosqlite.Connection, user_id: int) -> list:
    cursor = await db.execute(
        """SELECT provider, model_name,
               SUM(input_tokens), SUM(output_tokens), SUM(cost_usd), COUNT(*)
           FROM usage_log WHERE user_id = ?
           GROUP BY provider, model_name
           ORDER BY SUM(cost_usd) DESC""",
        (user_id,)
    )
    rows = await cursor.fetchall()
    return rows
