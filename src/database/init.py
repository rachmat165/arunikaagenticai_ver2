import sqlite3
import aiosqlite
from datetime import datetime
from pathlib import Path
from typing import Optional

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
                model_name TEXT DEFAULT 'claude-3-5-sonnet-20241022',
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
                model_name TEXT DEFAULT 'claude-3-5-sonnet-20241022',
                temperature REAL DEFAULT 0.7,
                max_tokens INTEGER DEFAULT 4096,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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

        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id)
        """)

        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_cron_user_id ON cron_jobs(user_id)
        """)

        await db.commit()

async def get_or_create_session(db: aiosqlite.Connection, user_id: int) -> int:
    cursor = await db.execute(
        "SELECT id FROM sessions WHERE user_id = ?",
        (user_id,)
    )
    row = await cursor.fetchone()

    if row:
        return row[0]

    cursor = await db.execute(
        "INSERT INTO sessions (user_id) VALUES (?)",
        (user_id,)
    )
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
        "SELECT role, content FROM messages WHERE session_id = ? ORDER BY timestamp DESC LIMIT ? ",
        (session_id, limit)
    )
    rows = await cursor.fetchall()
    return list(reversed(rows))

async def set_user_model(db: aiosqlite.Connection, user_id: int, provider: str, model_name: str):
    await db.execute(
        """INSERT INTO user_settings (user_id, model_provider, model_name, updated_at)
           VALUES (?, ?, ?, CURRENT_TIMESTAMP)
           ON CONFLICT(user_id) DO UPDATE SET model_provider = ?, model_name = ?, updated_at = CURRENT_TIMESTAMP""",
        (user_id, provider, model_name, provider, model_name)
    )
    await db.commit()

async def get_user_model(db: aiosqlite.Connection, user_id: int) -> tuple[str, str]:
    cursor = await db.execute(
        "SELECT model_provider, model_name FROM user_settings WHERE user_id = ?",
        (user_id,)
    )
    row = await cursor.fetchone()
    if row:
        return row
    return ("anthropic", "claude-3-5-sonnet-20241022")
