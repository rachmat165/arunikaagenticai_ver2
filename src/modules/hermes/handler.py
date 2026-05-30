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
MAX_TOOL_ROUNDS = 8

TOOL_ICONS = {
    "web_search":     "🌐",
    "read_file":      "📂",
    "write_file":     "💾",
    "remember":       "🧠",
    "run_python":     "🐍",
    "create_skill":   "⚡",
    "list_cron_jobs": "📋",
    "run_cron_job":   "⏰",
    "create_cron_job":"🗓️",
    "cancel_cron_job":"🗑️",
}

def _h(text: str) -> str:
    """Escape HTML special chars untuk Telegram HTML parse mode."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def _bar(done: int, total: int, width: int = 18) -> str:
    n = int(width * done / max(total, 1))
    return "█" * n + "░" * (width - n)

def _render_hermes_progress(
    task: str,
    round_num: int,
    total_rounds: int,
    current_tool: str,
    current_inp: dict,
    history: list,
    phase: str = "tool",
) -> str:
    task_short = (task[:65] + "…") if len(task) > 65 else task
    icon = TOOL_ICONS.get(current_tool, "🔧")
    bar  = _bar(round_num, total_rounds)
    pct  = int(100 * round_num / max(total_rounds, 1))

    inp_hint = ""
    for v in current_inp.values():
        s = str(v)
        if s:
            inp_hint = (s[:55] + "…") if len(s) > 55 else s
            break

    lines = [
        "🔮 <b>HERMES AGENT</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        f"💼 <i>{_h(task_short)}</i>",
        "",
        f"<code>[{bar}]</code>  {pct}%  •  Putaran {round_num}/{total_rounds}",
        "",
    ]

    if history or phase == "tool":
        lines.append("📋 <b>Riwayat Tool:</b>")
        for r, t, st in history:
            ti = TOOL_ICONS.get(t, "🔧")
            lines.append(f"  {st} Putaran {r} — {ti} <code>{_h(t)}</code>")
        if phase == "tool":
            lines.append(f"  🔄 Putaran {round_num} — {icon} <code>{_h(current_tool)}</code>")
            if inp_hint:
                lines.append(f"       📥 <code>{_h(inp_hint)}</code>")

    if phase == "finish":
        lines += ["", "✨ <b>Menyusun jawaban akhir...</b>"]
    elif phase == "start":
        lines += ["", "⚡ <i>Memulai — membuat rencana...</i>"]

    return "\n".join(lines)

HERMES_SYSTEM = """Anda adalah HERMES — agen AI otonom dari Reflective Koala ATG.

Anda memiliki akses ke tools berikut untuk menyelesaikan tugas:
- web_search: cari informasi di internet
- read_file: baca file dari PATH MANA SAJA (drive lokal, path absolut, relatif)
- write_file: tulis/simpan file teks
- generate_pdf: BUAT FILE PDF dan kirim ke Telegram — gunakan ini saat user minta PDF/laporan/dokumen
- remember: simpan fakta penting ke memori permanen
- run_python: jalankan kode Python
- create_skill: buat skill baru untuk bot
- list_cron_jobs: lihat daftar cron job / tugas terjadwal (Agen 24/7) yang sudah ada
- run_cron_job: JALANKAN cron job yang sudah ada sekarang (job_id tertentu / which='due' utk yang belum jalan / which='all')
- create_cron_job: buat tugas terjadwal baru
- cancel_cron_job: batalkan cron job

ATURAN CRON JOB / TUGAS TERJADWAL — WAJIB:
- Jika user minta "jalankan cron job yang belum jalan" → JANGAN beri tutorial crontab.
  Panggil list_cron_jobs dulu untuk melihat job yang ada, lalu run_cron_job (which='due'
  atau job_id tertentu) untuk benar-benar menjalankannya.
- Jangan pernah menyuruh user mengetik 'crontab -e' — bot ini memakai sistem Agen 24/7
  internal, bukan crontab Linux. Gunakan tools cron di atas.

KEMAMPUAN read_file:
✅ Bisa baca dari path absolut Windows: P:\\Folder\\file.pdf, C:\\Users\\nama\\doc.docx
✅ Bisa baca dari drive lain: D:\\, E:\\, P:\\, Q:\\, dll
✅ Bisa baca PDF, DOCX, XLSX, PPTX, TXT, CSV, JSON, PY, dll
✅ Gunakan path PERSIS seperti yang user berikan — jangan ubah path-nya

JANGAN PERNAH bilang:
❌ "Saya tidak bisa membuat PDF"
❌ "Saya tidak bisa membaca file dari path eksternal"
❌ "Akses saya terbatas ke direktori proyek"
❌ "Copy file ke proyek dulu" (jika path sudah diberikan)
Langsung gunakan tool yang sesuai.

ATURAN GENERATE PDF — WAJIB:
- Jika user meminta PDF/laporan/dokumen → langsung gunakan tool generate_pdf
- Masukkan SELURUH konten hasil riset ke parameter 'content' (jangan potong)
- Jangan tanya konfirmasi, jangan minta upload file — langsung generate

FORMAT TELEGRAM — WAJIB DIIKUTI PERMANEN:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TELEGRAM TIDAK RENDER: ## heading, | table |, ---, > blockquote
SELALU GUNAKAN FORMAT INI:

✅ HEADING → *JUDUL SECTION*
   Contoh: *📊 DATA OPERASIONAL*

✅ DIVIDER → ──────────────────────

✅ TABLE → WAJIB dalam code block:
   ```
   Kriteria          │ Nilai
   ──────────────────┼──────────
   Pengalaman        │ 14 tahun
   Jumlah Sekolah    │ 16 unit
   ```

✅ LIST → bullet • (bukan tanda minus -)
   • Item A
   • Item B

✅ BOLD → *teks*  (bukan **teks**)
✅ ITALIC → _teks_
✅ INLINE CODE → `kode`

❌ JANGAN GUNAKAN:
   × ## heading
   × | pipe | table |
   × --- divider
   × **double star**
   × Emoji berlebihan per section

PRINSIP HERMES:
1. Gunakan tools secara proaktif — jangan tebak, baca data langsung
2. Jika user menyebut path file → LANGSUNG panggil read_file dengan path tersebut
3. Buat skill baru jika menemukan pola yang bisa diulang
4. Simpan ke memori hal-hal yang user ingin diingat antar sesi
5. Laporkan progres secara transparan
6. SELALU format dokumen dengan struktur rapi & profesional

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
        on_file: Optional[Callable] = None,
        user_id: int = 0,
        memory=None,
        chat_id: int = 0,
        db_path: Optional[str] = None,
        agent_runner: Optional[Callable] = None,
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

        messages   = [{"role": "user", "content": task}]
        tool_round = 0
        final_text = ""
        history: list = []   # [(round, tool_name, status_emoji)]

        if on_progress:
            await on_progress(
                _render_hermes_progress(
                    task, 0, MAX_TOOL_ROUNDS, "", {}, history, phase="start"
                )
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

            text       = result.get("text", "")
            tool_calls = result.get("tool_calls", [])

            if text:
                final_text = text

            if not tool_calls:
                break

            # ── Eksekusi semua tool calls ────────────────────────────────────
            for tc in tool_calls:
                name = tc["name"]
                inp  = tc["input"]

                if on_progress:
                    await on_progress(
                        _render_hermes_progress(
                            task, tool_round, MAX_TOOL_ROUNDS,
                            name, inp, history, phase="tool"
                        )
                    )

                # Buat on_progress khusus untuk tool ini (misal Vision PDF)
                async def _tool_progress(msg: str, _op=on_progress):
                    if _op:
                        await _op(msg)

                tool_result = await self.executor.execute(
                    name, inp, router=router, on_progress=_tool_progress,
                    on_file=on_file, memory=memory,
                    db_path=db_path, user_id=user_id, chat_id=chat_id,
                    agent_runner=agent_runner,
                )

                history.append((tool_round, name, "✅"))
                _ = tool_result  # dipakai di bawah

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
                _render_hermes_progress(
                    task, tool_round, MAX_TOOL_ROUNDS,
                    "", {}, history, phase="finish"
                )
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
