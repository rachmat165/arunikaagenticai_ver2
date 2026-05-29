"""
Hermes Agent Handler — Agentic Loop dengan Tool Calling
Diadaptasi dari NousResearch/hermes-agent (github.com/NousResearch/hermes-agent)

Alur: User → Plan → [Tool Loop: call model → execute tools → call model] → Response
"""

import json
import logging
from typing import Optional, Callable

import aiosqlite

from src.config import settings
from src.modules.hermes.tools import TOOL_SCHEMAS, ToolExecutor, load_memory, load_skills_context

logger = logging.getLogger(__name__)
MAX_TOOL_ROUNDS = 8    # max berapa kali loop tool sebelum force-stop

HERMES_SYSTEM = """Anda adalah HERMES — agen AI otonom dari Reflective Koala ATG.

Anda memiliki akses ke tools berikut untuk menyelesaikan tugas:
- web_search: cari informasi di internet
- read_file: baca file dari proyek
- write_file: tulis/simpan file
- remember: simpan fakta penting ke memori permanen
- run_python: jalankan kode Python
- create_skill: buat skill baru untuk bot

PRINSIP HERMES:
1. Gunakan tools secara proaktif — jangan tebak, cari data nyata
2. Rencanakan langkah sebelum bertindak
3. Buat skill baru jika menemukan pola yang bisa diulang
4. Simpan ke memori hal-hal yang user ingin diingat antar sesi
5. Laporkan progres secara transparan

{memory_section}
{skills_section}"""


def _build_system(memory: str, skills: str) -> str:
    mem_sec = f"\n## MEMORI TERSIMPAN:\n{memory}" if memory.strip() else ""
    skill_sec = f"\n## SKILLS TERSEDIA:\n{skills}" if skills.strip() else ""
    return HERMES_SYSTEM.format(memory_section=mem_sec, skills_section=skill_sec)


def _schemas_to_openai(schemas: list) -> list:
    """Konversi Anthropic tool schema → OpenAI/OpenRouter format."""
    return [
        {
            "type": "function",
            "function": {
                "name": s["name"],
                "description": s["description"],
                "parameters": s["input_schema"],
            }
        }
        for s in schemas
    ]


class HermesHandler:
    def __init__(self):
        self.executor = ToolExecutor()

    async def run(
        self,
        task: str,
        router,
        on_progress: Optional[Callable] = None,
        user_id: int = 0,
    ) -> str:
        """
        Jalankan Hermes Agent Loop:
        1. Siapkan sistem prompt dengan memori & skills
        2. Panggil model dengan tools
        3. Jika ada tool call → eksekusi → masukkan hasil → ulangi
        4. Jika model berhenti memanggil tools → kembalikan respons akhir
        """
        memory = load_memory()
        skills = load_skills_context()
        system = _build_system(memory, skills)
        provider = router.provider

        messages = [{"role": "user", "content": task}]
        tool_round = 0
        final_text = ""

        if on_progress:
            await on_progress(
                f"🔮 *Hermes Agent*\n\n"
                f"📋 Tugas: `{task[:100]}`\n\n"
                f"⚡ Memulai agentic loop..."
            )

        while tool_round < MAX_TOOL_ROUNDS:
            tool_round += 1

            # ── Panggil model dengan tools ──────────────────────────────────
            try:
                if provider == "anthropic":
                    result = await self._call_anthropic_tools(
                        router, messages, system, TOOL_SCHEMAS
                    )
                else:
                    result = await self._call_openai_tools(
                        router, messages, system, TOOL_SCHEMAS
                    )
            except Exception as e:
                logger.exception("Hermes model call error: %s", e)
                return f"❌ Hermes gagal memanggil model: {e}"

            resp_type = result.get("type")
            text = result.get("text", "")
            tool_calls = result.get("tool_calls", [])

            # Tambahkan respons model ke messages
            if text:
                final_text = text

            if not tool_calls:
                # Model selesai — tidak ada tool lagi
                break

            # ── Eksekusi semua tool calls ────────────────────────────────────
            tool_summary_parts = []
            for tc in tool_calls:
                name = tc["name"]
                inp = tc["input"]

                if on_progress:
                    await on_progress(
                        f"🔮 *Hermes Agent*\n\n"
                        f"🔧 *Round {tool_round}* — Menjalankan tool:\n"
                        f"`{name}({json.dumps(inp, ensure_ascii=False)[:80]})`"
                    )

                tool_result = await self.executor.execute(name, inp)
                tool_summary_parts.append(f"**{name}**: {tool_result[:200]}")

                # Masukkan hasil tool ke messages (format sesuai provider)
                if provider == "anthropic":
                    messages.append({
                        "role": "assistant",
                        "content": [
                            {
                                "type": "tool_use",
                                "id": tc.get("id", f"tool_{tool_round}"),
                                "name": name,
                                "input": inp,
                            }
                        ],
                    })
                    messages.append({
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": tc.get("id", f"tool_{tool_round}"),
                                "content": tool_result,
                            }
                        ],
                    })
                else:
                    # OpenAI format
                    messages.append({
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": tc.get("id", f"call_{tool_round}"),
                                "type": "function",
                                "function": {
                                    "name": name,
                                    "arguments": json.dumps(inp),
                                },
                            }
                        ],
                    })
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.get("id", f"call_{tool_round}"),
                        "content": tool_result,
                    })

        if on_progress:
            await on_progress(
                f"🔮 *Hermes Agent*\n\n"
                f"✅ Selesai ({tool_round} round) — Menyusun respons..."
            )

        return final_text or "✅ Tugas selesai."

    async def _call_anthropic_tools(
        self, router, messages: list, system: str, schemas: list
    ) -> dict:
        """Panggil Anthropic API dengan tool use. Return {type, text, tool_calls}."""
        import httpx

        payload = {
            "model": router.model_name,
            "max_tokens": 4096,
            "system": system,
            "messages": messages,
            "tools": schemas,
        }

        assert router.client is not None
        resp = await router.client.post("/v1/messages", json=payload)
        if resp.status_code != 200:
            raise RuntimeError(f"Anthropic tool error {resp.status_code}: {resp.text[:300]}")

        data = resp.json()
        content = data.get("content", [])
        text = ""
        tool_calls = []

        for block in content:
            if block.get("type") == "text":
                text += block.get("text", "")
            elif block.get("type") == "tool_use":
                tool_calls.append({
                    "id": block.get("id"),
                    "name": block.get("name"),
                    "input": block.get("input", {}),
                })

        return {"text": text, "tool_calls": tool_calls}

    async def _call_openai_tools(
        self, router, messages: list, system: str, schemas: list
    ) -> dict:
        """Panggil OpenRouter/OpenAI API dengan tool use."""
        all_messages = [{"role": "system", "content": system}] + messages
        openai_tools = _schemas_to_openai(schemas)

        payload = {
            "model": router.model_name,
            "max_tokens": 4096,
            "messages": all_messages,
            "tools": openai_tools,
            "tool_choice": "auto",
        }

        assert router.client is not None
        resp = await router.client.post("/chat/completions", json=payload)
        if resp.status_code != 200:
            raise RuntimeError(f"OpenRouter tool error {resp.status_code}: {resp.text[:300]}")

        data = resp.json()
        choice = data["choices"][0]["message"]
        text = choice.get("content") or ""
        raw_tool_calls = choice.get("tool_calls") or []

        tool_calls = []
        for tc in raw_tool_calls:
            fn = tc.get("function", {})
            try:
                inp = json.loads(fn.get("arguments", "{}"))
            except Exception:
                inp = {}
            tool_calls.append({
                "id": tc.get("id"),
                "name": fn.get("name"),
                "input": inp,
            })

        return {"text": text, "tool_calls": tool_calls}

    async def recall(self, query: str, db_path: str, user_id: int) -> str:
        """Cari percakapan lama menggunakan LIKE search."""
        try:
            async with aiosqlite.connect(db_path) as db:
                # Cari di messages table
                cursor = await db.execute(
                    """
                    SELECT m.role, m.content, s.created_at
                    FROM messages m
                    JOIN sessions s ON m.session_id = s.id
                    WHERE s.user_id = ? AND m.content LIKE ?
                    ORDER BY m.id DESC
                    LIMIT 10
                    """,
                    (user_id, f"%{query}%"),
                )
                rows = await cursor.fetchall()
        except Exception as e:
            return f"❌ Gagal mencari: {e}"

        if not rows:
            return f"🔍 Tidak ada percakapan yang mengandung: *{query}*"

        lines = [f"🔍 *Hasil recall untuk: '{query}'* ({len(rows)} ditemukan)\n"]
        for role, content, created_at in rows:
            label = "👤 User" if role == "user" else "🤖 Dewi"
            snippet = content[:200].replace("\n", " ")
            lines.append(f"**{label}:** {snippet}...")

        return "\n".join(lines)
