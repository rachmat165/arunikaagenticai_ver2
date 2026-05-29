"""
24/7 Agent System — Agen yang berjalan terus-menerus tanpa interaksi user.
Diadaptasi dari konsep Letta (github.com/letta-ai/letta) — heartbeat & scheduled tasks.

Fitur:
  - Jadwalkan tugas yang berjalan otomatis (harian, mingguan, atau sekali)
  - Agen menjalankan tugas saat waktunya tiba
  - Hasilnya dikirim ke Telegram user
  - Mendukung format: "setiap hari HH:MM", "setiap senin HH:MM", "sekali YYYY-MM-DD HH:MM"
"""

import asyncio
import logging
import re
import uuid
from datetime import datetime, timedelta
from typing import Optional, Callable

import aiosqlite

from src.config import settings

logger = logging.getLogger(__name__)

SCHEDULE_PATTERNS = {
    "daily":   re.compile(r"setiap hari[,\s]+(\d{1,2}):(\d{2})", re.I),
    "weekly":  re.compile(r"setiap\s+(senin|selasa|rabu|kamis|jumat|sabtu|minggu)[,\s]+(\d{1,2}):(\d{2})", re.I),
    "once":    re.compile(r"sekali\s+(\d{4}-\d{2}-\d{2})\s+(\d{1,2}):(\d{2})", re.I),
    "hourly":  re.compile(r"setiap\s+(\d+)\s+jam", re.I),
}

DAY_MAP = {
    "senin": 0, "selasa": 1, "rabu": 2, "kamis": 3,
    "jumat": 4, "sabtu": 5, "minggu": 6,
}


def parse_schedule(schedule_str: str) -> Optional[datetime]:
    """Parse jadwal dari string natural language. Return datetime next_run."""
    now = datetime.now()

    # Setiap hari HH:MM
    m = SCHEDULE_PATTERNS["daily"].search(schedule_str)
    if m:
        h, mn = int(m.group(1)), int(m.group(2))
        next_run = now.replace(hour=h, minute=mn, second=0, microsecond=0)
        if next_run <= now:
            next_run += timedelta(days=1)
        return next_run

    # Setiap [hari] HH:MM
    m = SCHEDULE_PATTERNS["weekly"].search(schedule_str)
    if m:
        day_name = m.group(1).lower()
        h, mn = int(m.group(2)), int(m.group(3))
        target_dow = DAY_MAP.get(day_name, 0)
        days_ahead = (target_dow - now.weekday()) % 7
        if days_ahead == 0:
            candidate = now.replace(hour=h, minute=mn, second=0, microsecond=0)
            if candidate <= now:
                days_ahead = 7
        next_run = (now + timedelta(days=days_ahead)).replace(
            hour=h, minute=mn, second=0, microsecond=0
        )
        return next_run

    # Sekali YYYY-MM-DD HH:MM
    m = SCHEDULE_PATTERNS["once"].search(schedule_str)
    if m:
        date_str = m.group(1)
        h, mn = int(m.group(2)), int(m.group(3))
        try:
            dt = datetime.strptime(f"{date_str} {h:02d}:{mn:02d}", "%Y-%m-%d %H:%M")
            return dt
        except ValueError:
            return None

    # Setiap N jam
    m = SCHEDULE_PATTERNS["hourly"].search(schedule_str)
    if m:
        hours = int(m.group(1))
        return now + timedelta(hours=hours)

    return None


def compute_next_run(schedule_str: str, after: datetime) -> Optional[datetime]:
    """Hitung next_run berikutnya setelah eksekusi."""
    now_save = datetime.now()

    # Temporarily set "now" reference
    class _FakeNow:
        def __init__(self, dt):
            self._dt = dt
        def replace(self, **kw):
            return self._dt.replace(**kw)
        def __le__(self, other): return self._dt <= other

    # Daily
    m = SCHEDULE_PATTERNS["daily"].search(schedule_str)
    if m:
        h, mn = int(m.group(1)), int(m.group(2))
        next_run = after.replace(hour=h, minute=mn, second=0, microsecond=0)
        if next_run <= after:
            next_run += timedelta(days=1)
        return next_run

    # Weekly
    m = SCHEDULE_PATTERNS["weekly"].search(schedule_str)
    if m:
        day_name = m.group(1).lower()
        h, mn = int(m.group(2)), int(m.group(3))
        target_dow = DAY_MAP.get(day_name, 0)
        days_ahead = (target_dow - after.weekday()) % 7 or 7
        return (after + timedelta(days=days_ahead)).replace(
            hour=h, minute=mn, second=0, microsecond=0
        )

    # Hourly
    m = SCHEDULE_PATTERNS["hourly"].search(schedule_str)
    if m:
        hours = int(m.group(1))
        return after + timedelta(hours=hours)

    # Once — tidak berulang
    return None


class Agent24Runner:
    """
    Background runner yang memeriksa scheduled_tasks setiap menit
    dan menjalankan tugas yang sudah waktunya.
    """

    def __init__(
        self,
        db_path: str,
        agent_runner: Callable,    # async fn(user_id, task) → str
        message_sender: Callable,  # async fn(chat_id, text)
    ):
        self.db_path       = db_path
        self.agent_runner  = agent_runner
        self.message_sender = message_sender
        self._running      = False
        self._task: Optional[asyncio.Task] = None

    def start(self):
        if not self._running:
            self._running = True
            self._task = asyncio.create_task(self._loop())
            logger.info("Agent24 runner started")

    def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()

    async def _loop(self):
        while self._running:
            try:
                await self._check_and_run()
            except Exception as e:
                logger.exception("Agent24 loop error: %s", e)
            await asyncio.sleep(60)   # cek setiap 1 menit

    async def _check_and_run(self):
        now = datetime.now()
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """SELECT id, user_id, chat_id, task_desc, schedule
                   FROM scheduled_tasks
                   WHERE status = 'active' AND next_run <= ?""",
                (now.isoformat(),)
            )
            tasks = await cursor.fetchall()

        for task_id, user_id, chat_id, task_desc, schedule in tasks:
            await self._run_task(task_id, user_id, chat_id, task_desc, schedule)

    async def _run_task(self, task_id: str, user_id: int, chat_id: int,
                        task_desc: str, schedule: str):
        logger.info("Agent24 running task %s for user %d: %s", task_id, user_id, task_desc)
        now = datetime.now()

        try:
            result = await self.agent_runner(user_id, task_desc)
            await self.message_sender(
                chat_id,
                f"⏰ *Agen 24/7 — Tugas Otomatis*\n\n"
                f"📋 _{task_desc[:80]}_\n\n"
                f"{result}"
            )
            last_result = result[:500]
        except Exception as e:
            logger.exception("Agent24 task %s error: %s", task_id, e)
            last_result = f"Error: {e}"
            try:
                await self.message_sender(
                    chat_id,
                    f"⚠️ *Agen 24/7 — Tugas Gagal*\n\n"
                    f"📋 _{task_desc[:80]}_\n\n"
                    f"❌ {e}"
                )
            except Exception:
                pass

        # Update DB: last_run, next_run, last_result
        next_run = compute_next_run(schedule, now)
        async with aiosqlite.connect(self.db_path) as db:
            if next_run:
                await db.execute(
                    """UPDATE scheduled_tasks SET
                       last_run = ?, last_result = ?, next_run = ?
                       WHERE id = ?""",
                    (now.isoformat(), last_result, next_run.isoformat(), task_id)
                )
            else:
                # Tugas sekali → mark completed
                await db.execute(
                    """UPDATE scheduled_tasks SET
                       last_run = ?, last_result = ?, status = 'completed'
                       WHERE id = ?""",
                    (now.isoformat(), last_result, task_id)
                )
            await db.commit()


# ── CRUD helpers ─────────────────────────────────────────────────────────────

async def create_task(db_path: str, user_id: int, chat_id: int,
                      task_desc: str, schedule_str: str) -> dict:
    """Buat scheduled task baru. Return dict dengan info atau error."""
    next_run = parse_schedule(schedule_str)
    if not next_run:
        return {
            "error": (
                f"Format jadwal tidak dikenal: '{schedule_str}'\n\n"
                "Format yang didukung:\n"
                "• `setiap hari 08:00`\n"
                "• `setiap senin 09:00`\n"
                "• `setiap 2 jam`\n"
                "• `sekali 2026-06-01 10:00`"
            )
        }

    task_id = str(uuid.uuid4())[:8]
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """INSERT INTO scheduled_tasks
               (id, user_id, chat_id, task_desc, schedule, next_run)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (task_id, user_id, chat_id, task_desc, schedule_str, next_run.isoformat())
        )
        await db.commit()

    return {
        "id":       task_id,
        "task":     task_desc,
        "schedule": schedule_str,
        "next_run": next_run.strftime("%d %b %Y, %H:%M"),
    }


async def list_tasks(db_path: str, user_id: int) -> list:
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            """SELECT id, task_desc, schedule, next_run, last_run, status
               FROM scheduled_tasks WHERE user_id = ?
               ORDER BY next_run""",
            (user_id,)
        )
        return await cursor.fetchall()


async def cancel_task(db_path: str, task_id: str, user_id: int) -> bool:
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            "UPDATE scheduled_tasks SET status = 'cancelled' WHERE id = ? AND user_id = ?",
            (task_id, user_id)
        )
        await db.commit()
        return cursor.rowcount > 0
