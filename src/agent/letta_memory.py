"""
Letta-style Infinite Context Memory System
Diadaptasi dari github.com/letta-ai/letta (MemGPT)

Arsitektur 3-tier:
  1. Core Memory   — blok persona & human, selalu ada di system prompt, bisa diedit AI
  2. Archival Memory — penyimpanan tak terbatas via SQLite FTS5, bisa dicari AI
  3. Recall Memory — riwayat percakapan (sudah ada di ContextManager)

Tools yang bisa dipanggil AI:
  core_memory_append    — tambah ke blok core memory
  core_memory_replace   — edit/update blok core memory
  archival_memory_insert — simpan ke memori permanen
  archival_memory_search — cari di memori permanen
  conversation_search   — cari di riwayat percakapan
"""

import uuid
import json
import logging
from datetime import datetime
from typing import Optional

import aiosqlite

logger = logging.getLogger(__name__)

PERSONA_DEFAULT = """Saya adalah Dewi, AI Agent profesional milik PT. Arunika Teknologi Global (ATG).
Saya membantu dengan riset, penulisan dokumen, analisis bisnis, dan berbagai tugas kantor.
Saya ramah, kompeten, dan selalu memberikan jawaban yang actionable."""

HUMAN_DEFAULT = """Pengguna adalah anggota tim PT. Arunika Teknologi Global.
Preferensi dan informasi pengguna akan diperbarui seiring percakapan."""


# ─────────────────────────────────────────────────────────────────────────────
# TOOL SCHEMAS (format Anthropic — dipakai di chat() dan Hermes)
# ─────────────────────────────────────────────────────────────────────────────

MEMORY_TOOL_SCHEMAS = [
    {
        "name": "core_memory_append",
        "description": (
            "Tambahkan informasi ke blok core memory (persona atau human). "
            "Gunakan ini untuk menyimpan fakta penting tentang user atau tentang diri bot "
            "yang harus diingat di setiap percakapan. Memory ini SELALU ada di system prompt."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "enum": ["persona", "human"],
                    "description": "'human' untuk fakta tentang user, 'persona' untuk tentang bot/ATG"
                },
                "content": {
                    "type": "string",
                    "description": "Informasi yang akan ditambahkan ke blok memori"
                }
            },
            "required": ["name", "content"]
        }
    },
    {
        "name": "core_memory_replace",
        "description": (
            "Update/koreksi isi blok core memory dengan mengganti teks lama → baru. "
            "Gunakan saat informasi yang tersimpan sudah tidak akurat atau perlu diperbarui."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name":    {"type": "string", "enum": ["persona", "human"]},
                "old_str": {"type": "string", "description": "Teks yang akan diganti (harus persis sama)"},
                "new_str": {"type": "string", "description": "Teks pengganti"}
            },
            "required": ["name", "old_str", "new_str"]
        }
    },
    {
        "name": "archival_memory_insert",
        "description": (
            "Simpan informasi ke Archival Memory (memori jangka panjang tanpa batas). "
            "Gunakan untuk fakta penting, keputusan, hasil riset, atau konten yang mungkin "
            "dibutuhkan di masa depan tapi terlalu panjang untuk core memory."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Isi yang akan disimpan"},
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Tag untuk memudahkan pencarian, contoh: ['keuangan', 'Q1-2026', 'mitra']"
                }
            },
            "required": ["content"]
        }
    },
    {
        "name": "archival_memory_search",
        "description": (
            "Cari di Archival Memory menggunakan full-text search. "
            "Gunakan saat user bertanya tentang sesuatu yang mungkin pernah disimpan sebelumnya."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query":   {"type": "string", "description": "Kata kunci pencarian"},
                "tag":     {"type": "string", "description": "Filter berdasarkan tag (opsional)"},
                "limit":   {"type": "integer", "description": "Maksimal hasil (default 5)", "default": 5}
            },
            "required": ["query"]
        }
    },
    {
        "name": "conversation_search",
        "description": (
            "Cari di riwayat percakapan sebelumnya. "
            "Gunakan saat user merujuk ke topik yang pernah dibahas di sesi lain."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Kata kunci pencarian di riwayat chat"},
                "limit": {"type": "integer", "description": "Maksimal hasil (default 5)", "default": 5}
            },
            "required": ["query"]
        }
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# LettaMemory Class
# ─────────────────────────────────────────────────────────────────────────────

class LettaMemory:
    """
    Manajemen memori Letta-style untuk satu user.
    Core Memory + Archival Memory menggunakan SQLite.
    """

    def __init__(self, user_id: int, db_path: str):
        self.user_id  = user_id
        self.db_path  = db_path
        self._persona = ""
        self._human   = ""
        self._loaded  = False

    # ── Load / Save ──────────────────────────────────────────────────────────

    async def ensure_loaded(self):
        if self._loaded:
            return
        await self._load_from_db()

    async def _load_from_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT label, value FROM memory_blocks WHERE user_id = ?",
                (self.user_id,)
            )
            rows = await cursor.fetchall()

        blocks = {r[0]: r[1] for r in rows}
        self._persona = blocks.get("persona", PERSONA_DEFAULT)
        self._human   = blocks.get("human",   HUMAN_DEFAULT)
        self._loaded  = True

    async def _save_block(self, label: str, value: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT INTO memory_blocks (id, user_id, label, value, edited_at)
                   VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(user_id, label) DO UPDATE SET
                       value = excluded.value,
                       edited_at = CURRENT_TIMESTAMP""",
                (str(uuid.uuid4()), self.user_id, label, value)
            )
            await db.commit()

    # ── Compile for System Prompt ─────────────────────────────────────────────

    async def compile_for_prompt(self) -> str:
        await self.ensure_loaded()
        archival_count = await self._count_archival()
        now = datetime.now().strftime("%d %b %Y, %H:%M")
        return (
            "\n\n<memory_blocks>\n"
            f"<persona>\n{self._persona}\n</persona>\n\n"
            f"<human>\n{self._human}\n</human>\n"
            "</memory_blocks>\n\n"
            "<memory_metadata>\n"
            f"  - Waktu sekarang: {now}\n"
            f"  - Archival memory: {archival_count} entri tersimpan\n"
            "  - Anda bisa mengedit core memory dan menyimpan ke archival memory kapan saja\n"
            "</memory_metadata>"
        )

    async def _count_archival(self) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM passages WHERE user_id = ?", (self.user_id,)
            )
            row = await cursor.fetchone()
            return row[0] if row else 0

    # ── Core Memory Tools ─────────────────────────────────────────────────────

    async def core_memory_append(self, name: str, content: str) -> str:
        await self.ensure_loaded()
        limit = 5000
        if name == "persona":
            if len(self._persona) + len(content) + 1 > limit:
                return f"❌ Core memory '{name}' penuh ({limit} karakter). Gunakan core_memory_replace untuk menghapus yang tidak perlu dulu."
            self._persona += f"\n{content}"
            await self._save_block("persona", self._persona)
            return f"✅ Ditambahkan ke core memory 'persona' ({len(self._persona)} / {limit} karakter)"
        elif name == "human":
            if len(self._human) + len(content) + 1 > limit:
                return f"❌ Core memory '{name}' penuh. Gunakan core_memory_replace untuk memperbarui."
            self._human += f"\n{content}"
            await self._save_block("human", self._human)
            return f"✅ Ditambahkan ke core memory 'human' ({len(self._human)} / {limit} karakter)"
        return f"❌ Blok memori '{name}' tidak dikenal. Gunakan 'persona' atau 'human'."

    async def core_memory_replace(self, name: str, old_str: str, new_str: str) -> str:
        await self.ensure_loaded()
        if name == "persona":
            if old_str not in self._persona:
                return f"❌ Teks '{old_str[:50]}...' tidak ditemukan di blok 'persona'."
            self._persona = self._persona.replace(old_str, new_str, 1)
            await self._save_block("persona", self._persona)
            return "✅ Core memory 'persona' berhasil diperbarui."
        elif name == "human":
            if old_str not in self._human:
                return f"❌ Teks '{old_str[:50]}...' tidak ditemukan di blok 'human'."
            self._human = self._human.replace(old_str, new_str, 1)
            await self._save_block("human", self._human)
            return "✅ Core memory 'human' berhasil diperbarui."
        return f"❌ Blok '{name}' tidak dikenal."

    # ── Archival Memory Tools ─────────────────────────────────────────────────

    async def archival_memory_insert(self, content: str, tags: list = None) -> str:
        tags_json = json.dumps(tags or [], ensure_ascii=False)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO passages (id, user_id, content, tags) VALUES (?, ?, ?, ?)",
                (str(uuid.uuid4()), self.user_id, content, tags_json)
            )
            await db.commit()
        tag_str = ", ".join(tags) if tags else "(tanpa tag)"
        return f"✅ Disimpan ke Archival Memory [{tag_str}]: {content[:60]}..."

    async def archival_memory_search(self, query: str, tag: str = None, limit: int = 5) -> str:
        limit = min(limit, 10)
        async with aiosqlite.connect(self.db_path) as db:
            if tag:
                cursor = await db.execute(
                    """SELECT p.content, p.tags, p.created_at
                       FROM passages p
                       WHERE p.user_id = ? AND p.tags LIKE ?
                       ORDER BY p.created_at DESC LIMIT ?""",
                    (self.user_id, f'%{tag}%', limit)
                )
            else:
                # FTS5 search
                try:
                    cursor = await db.execute(
                        """SELECT p.content, p.tags, p.created_at
                           FROM passages p
                           JOIN passages_fts f ON p.rowid = f.rowid
                           WHERE p.user_id = ? AND passages_fts MATCH ?
                           ORDER BY rank LIMIT ?""",
                        (self.user_id, query, limit)
                    )
                except Exception:
                    # Fallback to LIKE search
                    cursor = await db.execute(
                        """SELECT content, tags, created_at FROM passages
                           WHERE user_id = ? AND content LIKE ?
                           ORDER BY created_at DESC LIMIT ?""",
                        (self.user_id, f"%{query}%", limit)
                    )
            rows = await cursor.fetchall()

        if not rows:
            return f"🔍 Tidak ada memori ditemukan untuk: '{query}'"

        lines = [f"🔍 Ditemukan {len(rows)} memori untuk '{query}':"]
        for i, (content, tags_json, created_at) in enumerate(rows, 1):
            try:
                tags_list = json.loads(tags_json or "[]")
            except Exception:
                tags_list = []
            tag_str = " ".join(f"[{t}]" for t in tags_list) if tags_list else ""
            date_str = str(created_at)[:10] if created_at else ""
            lines.append(f"\n{i}. {tag_str} ({date_str})\n   {content[:300]}")
        return "\n".join(lines)

    async def conversation_search(self, query: str, limit: int = 5) -> str:
        limit = min(limit, 10)
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """SELECT m.role, m.content, m.timestamp
                   FROM messages m
                   JOIN sessions s ON m.session_id = s.id
                   WHERE s.user_id = ? AND m.content LIKE ?
                   ORDER BY m.timestamp DESC LIMIT ?""",
                (self.user_id, f"%{query}%", limit)
            )
            rows = await cursor.fetchall()

        if not rows:
            return f"🔍 Tidak ada percakapan ditemukan untuk: '{query}'"

        lines = [f"💬 Ditemukan {len(rows)} percakapan untuk '{query}':"]
        for role, content, ts in rows:
            label  = "👤 Anda" if role == "user" else "🤖 Dewi"
            date_s = str(ts)[:16] if ts else ""
            lines.append(f"\n{label} ({date_s}):\n   {content[:200]}")
        return "\n".join(lines)

    # ── Execute Tool (single interface) ──────────────────────────────────────

    async def execute_tool(self, tool_name: str, tool_input: dict) -> str:
        """Eksekusi satu memory tool call. Return string result."""
        try:
            if tool_name == "core_memory_append":
                return await self.core_memory_append(**tool_input)
            elif tool_name == "core_memory_replace":
                return await self.core_memory_replace(**tool_input)
            elif tool_name == "archival_memory_insert":
                return await self.archival_memory_insert(**tool_input)
            elif tool_name == "archival_memory_search":
                return await self.archival_memory_search(**tool_input)
            elif tool_name == "conversation_search":
                return await self.conversation_search(**tool_input)
            else:
                return f"❌ Tool '{tool_name}' tidak dikenal."
        except Exception as e:
            logger.exception("Memory tool %s error: %s", tool_name, e)
            return f"❌ Error: {e}"

    # ── Stats & Display ───────────────────────────────────────────────────────

    async def get_stats(self) -> dict:
        await self.ensure_loaded()
        archival = await self._count_archival()
        return {
            "persona_chars": len(self._persona),
            "human_chars":   len(self._human),
            "archival_count": archival,
            "persona": self._persona,
            "human":   self._human,
        }

    async def get_archival_entries(self, limit: int = 20) -> list:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """SELECT content, tags, created_at FROM passages
                   WHERE user_id = ? ORDER BY created_at DESC LIMIT ?""",
                (self.user_id, limit)
            )
            return await cursor.fetchall()

    async def clear_archival(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM passages WHERE user_id = ?", (self.user_id,))
            await db.commit()

    async def clear_core(self, label: str = None):
        await self.ensure_loaded()
        if label == "persona" or label is None:
            self._persona = PERSONA_DEFAULT
            await self._save_block("persona", self._persona)
        if label == "human" or label is None:
            self._human = HUMAN_DEFAULT
            await self._save_block("human", self._human)


# ─────────────────────────────────────────────────────────────────────────────
# MEMORY TOOL SCHEMAS — OpenAI/OpenRouter format (untuk Hermes via OpenRouter)
# ─────────────────────────────────────────────────────────────────────────────

def memory_schemas_to_openai() -> list:
    return [
        {
            "type": "function",
            "function": {
                "name": s["name"],
                "description": s["description"],
                "parameters": s["input_schema"],
            }
        }
        for s in MEMORY_TOOL_SCHEMAS
    ]
