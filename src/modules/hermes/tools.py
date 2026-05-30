"""
Hermes Agent — Built-in Tools
Diadaptasi dari NousResearch/hermes-agent (github.com/NousResearch/hermes-agent)

Tools: web_search, read_file, write_file, remember, run_python, recall_memory
"""

import json
import logging
from pathlib import Path
from typing import Any

from src.config import settings
from src.tools.firecrawl import FirecrawlClient
from src.tools.code_executor import execute_python
from src.agent.letta_memory import MEMORY_TOOL_SCHEMAS as _LETTA_SCHEMAS

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
MEMORY_FILE  = PROJECT_ROOT / "data" / "hermes_memory.md"

# ── Tool schemas (format Anthropic — dikonversi ke OpenAI oleh model_router) ──

# Gabungkan Hermes tools + Letta Memory tools
TOOL_SCHEMAS = _LETTA_SCHEMAS + [
    {
        "name": "web_search",
        "description": "Cari informasi di internet menggunakan Firecrawl. Gunakan untuk mendapatkan data terkini, riset, berita, atau informasi yang tidak kamu ketahui.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "query pencarian yang spesifik dan relevan"
                },
                "limit": {
                    "type": "integer",
                    "description": "jumlah hasil (default 3, max 5)",
                    "default": 3
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "read_file",
        "description": (
            "Baca isi file dari MANA SAJA — proyek bot, drive lokal, atau path absolut. "
            "Mendukung: PDF, DOCX, XLSX, PPTX, TXT, MD, CSV, JSON, PY, dan format teks lainnya. "
            "Gunakan path PERSIS seperti yang user berikan, termasuk drive letter Windows."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": (
                        "Path file. Bisa berupa: "
                        "path absolut Windows (contoh: P:\\Folder\\file.pdf atau C:/Users/nama/file.docx), "
                        "UNC path (\\\\server\\share\\file), "
                        "atau path relatif dari root proyek (contoh: src/config.py, data/laporan.pdf)"
                    )
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "write_file",
        "description": "Tulis atau simpan konten ke file. Gunakan untuk membuat skill baru, menyimpan output, atau membuat dokumen.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "path file relatif dari root proyek"
                },
                "content": {
                    "type": "string",
                    "description": "isi konten yang akan ditulis"
                }
            },
            "required": ["path", "content"]
        }
    },
    {
        "name": "remember",
        "description": "Simpan fakta penting ke memori permanen. Gunakan untuk mengingat preferensi user, keputusan penting, atau informasi yang perlu diingat di sesi berikutnya.",
        "input_schema": {
            "type": "object",
            "properties": {
                "fact": {
                    "type": "string",
                    "description": "fakta yang perlu diingat"
                },
                "category": {
                    "type": "string",
                    "description": "kategori memori: user, project, decision, skill",
                    "enum": ["user", "project", "decision", "skill"]
                }
            },
            "required": ["fact"]
        }
    },
    {
        "name": "run_python",
        "description": "Jalankan kode Python dalam venv bot. Gunakan untuk kalkulasi, manipulasi data, atau mengetes logika.",
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "kode Python yang akan dieksekusi"
                }
            },
            "required": ["code"]
        }
    },
    {
        "name": "generate_pdf",
        "description": (
            "Buat file PDF dari judul dan konten teks/markdown lalu kirim ke Telegram. "
            "WAJIB gunakan tool ini ketika user meminta membuat PDF, laporan, atau dokumen "
            "dari hasil riset/analisis yang baru saja dibuat dalam percakapan ini."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "judul dokumen PDF (singkat dan deskriptif)"
                },
                "content": {
                    "type": "string",
                    "description": "isi konten lengkap dalam format Markdown"
                },
                "subtitle": {
                    "type": "string",
                    "description": "sub-judul opsional"
                }
            },
            "required": ["title", "content"]
        }
    },
    {
        "name": "create_skill",
        "description": "Buat skill baru untuk bot ini. Skill adalah file Markdown yang mendefinisikan panduan atau prosedur untuk tugas tertentu.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "nama skill (tanpa spasi, gunakan-dash)"
                },
                "description": {
                    "type": "string",
                    "description": "deskripsi singkat apa yang dilakukan skill ini"
                },
                "content": {
                    "type": "string",
                    "description": "isi skill dalam format Markdown — panduan, langkah, atau prosedur"
                }
            },
            "required": ["name", "description", "content"]
        }
    },
    {
        "name": "list_cron_jobs",
        "description": (
            "Lihat daftar cron job / tugas terjadwal milik user (sistem Agen 24/7). "
            "Gunakan untuk mengetahui job apa saja yang sudah dijadwalkan, jam berapa, "
            "kapan terakhir jalan (last_run), dan kapan jadwal berikutnya (next_run). "
            "WAJIB panggil ini dulu saat user menyebut 'cron job yang sudah ada', "
            "'tugas terjadwal', atau ingin menjalankan job yang belum jalan."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "run_cron_job",
        "description": (
            "Jalankan SEKARANG cron job yang sudah terjadwal (eksekusi tugasnya secara nyata). "
            "Pilih salah satu: 'job_id' untuk satu job tertentu, atau 'which'='due' untuk "
            "semua job aktif yang sudah jatuh tempo / belum jalan, atau 'which'='all' untuk "
            "semua job aktif. Gunakan saat user minta 'jalankan cron job yang belum jalan'. "
            "Setelah dijalankan, last_run & next_run diperbarui otomatis."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "job_id": {
                    "type": "string",
                    "description": "ID job (8 karakter) yang ingin dijalankan. Kosongkan jika memakai 'which'.",
                },
                "which": {
                    "type": "string",
                    "enum": ["due", "all"],
                    "description": "'due' = semua job aktif yang next_run <= sekarang (belum jalan); 'all' = semua job aktif.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "create_cron_job",
        "description": (
            "Buat cron job / tugas terjadwal baru untuk Agen 24/7. "
            "Format jadwal yang didukung: 'setiap hari 08:00', 'setiap senin 09:00', "
            "'setiap 2 jam', 'sekali 2026-06-01 10:00'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "task_desc": {
                    "type": "string",
                    "description": "deskripsi tugas yang akan dijalankan otomatis sesuai jadwal",
                },
                "schedule": {
                    "type": "string",
                    "description": "jadwal natural language, mis. 'setiap hari 09:00'",
                },
            },
            "required": ["task_desc", "schedule"],
        },
    },
    {
        "name": "cancel_cron_job",
        "description": "Batalkan/hapus cron job berdasarkan job_id (ambil id dari list_cron_jobs).",
        "input_schema": {
            "type": "object",
            "properties": {
                "job_id": {"type": "string", "description": "ID job (8 karakter) yang akan dibatalkan"},
            },
            "required": ["job_id"],
        },
    },
]


class ToolExecutor:
    def __init__(self):
        self._fc = (
            FirecrawlClient(settings.firecrawl_api_key)
            if settings.firecrawl_api_key else None
        )

    async def execute(self, tool_name: str, tool_input: dict, router=None, on_progress=None, on_file=None, memory=None,
                      db_path=None, user_id: int = 0, chat_id: int = 0, agent_runner=None) -> str:
        """Eksekusi satu tool call. Return string hasil."""
        try:
            # ── Letta Memory Tools ───────────────────────────────────────────
            if tool_name in ("core_memory_append", "core_memory_replace",
                             "archival_memory_insert", "archival_memory_search",
                             "conversation_search"):
                if memory is None:
                    return "❌ Memory tidak tersedia dalam sesi ini."
                return await memory.execute_tool(tool_name, tool_input)

            if tool_name == "web_search":
                return await self._web_search(**tool_input)
            elif tool_name == "read_file":
                return await self._read_file_async(router=router, on_progress=on_progress, **tool_input)
            elif tool_name == "write_file":
                return self._write_file(**tool_input)
            elif tool_name == "remember":
                return self._remember(**tool_input)
            elif tool_name == "run_python":
                return await self._run_python(**tool_input)
            elif tool_name == "generate_pdf":
                return await self._generate_pdf(on_file=on_file, **tool_input)
            elif tool_name == "create_skill":
                return self._create_skill(**tool_input)
            # ── Cron / Agen 24/7 Tools ───────────────────────────────────────
            elif tool_name == "list_cron_jobs":
                return await self._list_cron_jobs(db_path, user_id)
            elif tool_name == "run_cron_job":
                return await self._run_cron_job(db_path, user_id, agent_runner,
                                                on_progress=on_progress, **tool_input)
            elif tool_name == "create_cron_job":
                return await self._create_cron_job(db_path, user_id, chat_id, **tool_input)
            elif tool_name == "cancel_cron_job":
                return await self._cancel_cron_job(db_path, user_id, **tool_input)
            else:
                return f"❌ Tool '{tool_name}' tidak dikenal."
        except Exception as e:
            logger.exception("Tool %s error: %s", tool_name, e)
            return f"❌ Error menjalankan tool {tool_name}: {e}"

    # ── Cron / Agen 24/7 tool handlers ──────────────────────────────────────
    async def _list_cron_jobs(self, db_path, user_id: int) -> str:
        if not db_path:
            return "❌ Akses cron job tidak tersedia dalam sesi ini."
        from src.agent.agent24 import list_tasks
        rows = await list_tasks(db_path, user_id)
        if not rows:
            return "📭 Belum ada cron job / tugas terjadwal. Buat dengan create_cron_job."
        lines = [f"📋 Ada {len(rows)} cron job:"]
        for (id_, desc, schedule, next_run, last_run, status) in rows:
            nr = (next_run or "")[:16].replace("T", " ")
            lr = (last_run or "")[:16].replace("T", " ") if last_run else "belum pernah"
            lines.append(
                f"• [{id_}] {str(desc)[:60]}\n"
                f"   jadwal: {schedule} | berikutnya: {nr} | terakhir: {lr} | status: {status}"
            )
        return "\n".join(lines)

    async def _run_cron_job(self, db_path, user_id: int, agent_runner,
                            job_id: str = "", which: str = "", on_progress=None) -> str:
        if not db_path:
            return "❌ Akses cron job tidak tersedia dalam sesi ini."
        if agent_runner is None:
            return "❌ Runner tidak tersedia untuk menjalankan job dalam sesi ini."
        from datetime import datetime
        import aiosqlite
        from src.agent.agent24 import list_tasks, compute_next_run

        rows = await list_tasks(db_path, user_id)
        now = datetime.now()
        selected = []
        for (id_, desc, schedule, next_run, last_run, status) in rows:
            if status != "active":
                continue
            if job_id:
                if id_ == job_id:
                    selected.append((id_, desc, schedule))
                    break
                continue
            if which == "all":
                selected.append((id_, desc, schedule))
            else:  # default 'due' — belum jalan / sudah jatuh tempo
                try:
                    is_due = bool(next_run) and datetime.fromisoformat(next_run) <= now
                except Exception:
                    is_due = True
                if is_due:
                    selected.append((id_, desc, schedule))

        if not selected:
            if job_id:
                return f"❌ Cron job '{job_id}' tidak ditemukan / tidak aktif."
            return "✅ Tidak ada cron job yang perlu dijalankan (semua sudah up-to-date)."

        results = []
        for idx, (id_, desc, schedule) in enumerate(selected, start=1):
            if on_progress:
                try:
                    await on_progress(f"⏰ Menjalankan cron job {idx}/{len(selected)}: {str(desc)[:50]}…")
                except Exception:
                    pass
            try:
                out = await agent_runner(user_id, desc)
            except Exception as e:
                out = f"Error: {e}"
            out_str = str(out)
            # Perbarui last_run + next_run (atau completed untuk 'sekali')
            nr = compute_next_run(schedule, now)
            async with aiosqlite.connect(db_path) as db:
                if nr:
                    await db.execute(
                        "UPDATE scheduled_tasks SET last_run=?, last_result=?, next_run=? WHERE id=?",
                        (now.isoformat(), out_str[:500], nr.isoformat(), id_),
                    )
                else:
                    await db.execute(
                        "UPDATE scheduled_tasks SET last_run=?, last_result=?, status='completed' WHERE id=?",
                        (now.isoformat(), out_str[:500], id_),
                    )
                await db.commit()
            results.append(f"▶️ [{id_}] {str(desc)[:50]}\n{out_str[:900]}")

        header = f"✅ Selesai menjalankan {len(selected)} cron job:\n"
        return header + "\n\n".join(results)

    async def _create_cron_job(self, db_path, user_id: int, chat_id: int,
                               task_desc: str, schedule: str) -> str:
        if not db_path:
            return "❌ Akses cron job tidak tersedia dalam sesi ini."
        from src.agent.agent24 import create_task
        res = await create_task(db_path, user_id, chat_id, task_desc, schedule)
        if "error" in res:
            return f"❌ {res['error']}"
        return (
            f"✅ Cron job dibuat!\n"
            f"• ID: {res['id']}\n"
            f"• Tugas: {res['task']}\n"
            f"• Jadwal: {res['schedule']}\n"
            f"• Jalan berikutnya: {res['next_run']}"
        )

    async def _cancel_cron_job(self, db_path, user_id: int, job_id: str) -> str:
        if not db_path:
            return "❌ Akses cron job tidak tersedia dalam sesi ini."
        from src.agent.agent24 import cancel_task
        ok = await cancel_task(db_path, job_id, user_id)
        return f"✅ Cron job '{job_id}' dibatalkan." if ok else f"❌ Cron job '{job_id}' tidak ditemukan."

    async def _generate_pdf(self, title: str, content: str, subtitle: str = "", on_file=None) -> str:
        """Generate PDF dari konten dan opsional kirim ke Telegram via on_file callback."""
        from src.tools.general_pdf import generate_document_pdf_async
        path = await generate_document_pdf_async(title, content, subtitle=subtitle)
        p = Path(path)
        size_kb = p.stat().st_size // 1024
        if on_file:
            await on_file(path)
        return (
            f"✅ PDF *{title}* berhasil dibuat!\n"
            f"📄 {p.name} ({size_kb} KB)\n"
            f"📤 File dikirim ke Telegram."
        )

    async def _web_search(self, query: str, limit: int = 3) -> str:
        if not self._fc:
            return "❌ Firecrawl tidak dikonfigurasi. Set FIRECRAWL_API_KEY di .env"
        results = await self._fc.search(query, limit=min(limit, 5))
        if not results:
            return f"Tidak ada hasil untuk: {query}"
        return self._fc.format_search_results(results, max_chars_each=2000)

    def _read_file(self, path: str) -> str:
        # Resolve path — absolute (termasuk Windows drive letter) atau relatif
        file_path = Path(path)
        if not file_path.is_absolute():
            # Coba juga sebagai Windows path jika ada drive letter (P:\...)
            if len(path) >= 3 and path[1] == ":" and path[2] in ("/", "\\"):
                file_path = Path(path)
            else:
                file_path = PROJECT_ROOT / path.lstrip("/").lstrip("\\")

        if not file_path.exists():
            return (
                f"❌ File tidak ditemukan: `{path}`\n\n"
                f"Path yang dicoba: `{file_path}`\n"
                f"Pastikan path benar dan drive/folder bisa diakses dari komputer ini."
            )

        ext = file_path.suffix.lower()
        size = file_path.stat().st_size

        # Gambar → arahkan ke vision
        from src.tools.file_reader import SUPPORTED_IMG
        if ext in SUPPORTED_IMG:
            return (
                f"📸 File `{file_path.name}` adalah gambar ({ext.upper()}).\n"
                f"Untuk menganalisis gambar, kirim file tersebut langsung ke chat Telegram "
                f"sebagai foto atau file — bot akan menganalisis dengan Vision AI."
            )

        # PDF, DOCX, XLSX, PPTX — gunakan extractor
        from src.tools.file_reader import (
            SUPPORTED_PDF, SUPPORTED_DOCX, SUPPORTED_XLSX, SUPPORTED_PPTX,
            _read_pdf, _read_docx, _read_xlsx, _read_pptx, _read_text,
            SUPPORTED_TEXT,
        )

        try:
            if ext in SUPPORTED_PDF:
                result = _read_pdf(str(file_path))
            elif ext in SUPPORTED_DOCX:
                result = _read_docx(str(file_path))
            elif ext in SUPPORTED_XLSX:
                result = _read_xlsx(str(file_path))
            elif ext in SUPPORTED_PPTX:
                result = _read_pptx(str(file_path))
            elif ext in SUPPORTED_TEXT or size < 500_000:
                result = _read_text(str(file_path))
            else:
                return (
                    f"⚠️ Format `{ext}` tidak didukung untuk ekstraksi teks.\n"
                    f"Format yang didukung: PDF, DOCX, XLSX, PPTX, TXT, MD, CSV, JSON, PY, dll."
                )
        except Exception as e:
            return f"❌ Gagal membaca file: {e}"

        if "error" in result:
            return f"❌ {result['error']}"

        pages = result.get("pages", 1)
        text = result.get("text", "")
        fname = file_path.name
        return (
            f"📄 **{fname}** ({ext.upper()}, {pages} halaman, {len(text):,} karakter)\n"
            f"Path: `{file_path}`\n\n"
            f"---\n{text}"
        )

    async def _read_file_async(self, path: str, router=None, on_progress=None) -> str:
        """Wrapper async untuk _read_file — otomatis fallback ke Vision jika PDF scan."""
        import asyncio

        # Resolve path
        file_path = Path(path)
        if not file_path.is_absolute():
            if len(path) >= 3 and path[1] == ":" and path[2] in ("/", "\\"):
                file_path = Path(path)
            else:
                file_path = PROJECT_ROOT / path.lstrip("/").lstrip("\\")

        if not file_path.exists():
            return (
                f"❌ File tidak ditemukan: `{path}`\n"
                f"Path yang dicoba: `{file_path}`"
            )

        ext = file_path.suffix.lower()
        from src.tools.file_reader import SUPPORTED_PDF, SUPPORTED_IMG

        # Gambar → arahkan ke vision
        if ext in SUPPORTED_IMG:
            return (
                f"📸 File `{file_path.name}` adalah gambar ({ext.upper()}).\n"
                "Kirim file ini langsung ke chat Telegram sebagai foto/file "
                "agar dianalisis dengan Vision AI."
            )

        # PDF → coba ekstrak teks, fallback ke Vision jika scan
        if ext in SUPPORTED_PDF:
            from src.tools.file_reader import _read_pdf
            result = await asyncio.to_thread(_read_pdf, str(file_path))
            if "error" in result:
                err = result["error"]
                # Deteksi PDF scan → gunakan Vision AI
                if ("scan" in err.lower() or "gambar" in err.lower()
                        or "tidak mengandung teks" in err.lower()):
                    if router:
                        return await self._read_pdf_via_vision(file_path, router, on_progress=on_progress)
                    return (
                        f"⚠️ PDF ini adalah scan/gambar.\n"
                        f"Gunakan `/h` dengan model yang mendukung Vision "
                        f"(Claude atau GPT-4o) agar bot bisa membacanya."
                    )
                return f"❌ {err}"
            pages = result.get("pages", 1)
            text  = result.get("text", "")
            return (
                f"📄 **{file_path.name}** (PDF, {pages} hal, {len(text):,} kar)\n"
                f"Path: `{file_path}`\n\n---\n{text}"
            )

        # Format lain — gunakan _read_file sync
        return await asyncio.to_thread(self._read_file, path)

    async def _read_pdf_via_vision(self, file_path: Path, router, on_progress=None) -> str:
        """Render halaman PDF scan sebagai gambar → analisis tiap halaman via Vision AI."""
        import base64
        import io
        import asyncio

        try:
            import pypdfium2 as pdfium
            from PIL import Image
        except ImportError as e:
            return f"❌ Library tidak tersedia untuk render PDF: {e}"

        try:
            def _render_pages():
                pdf = pdfium.PdfDocument(str(file_path))
                n_pages = len(pdf)
                pages_b64 = []
                for i in range(min(n_pages, 15)):   # maks 15 halaman
                    page = pdf[i]
                    bitmap = page.render(scale=150 / 72)   # 150 DPI
                    pil_img = bitmap.to_pil()
                    buf = io.BytesIO()
                    pil_img.save(buf, format="JPEG", quality=80)
                    pages_b64.append(base64.b64encode(buf.getvalue()).decode())
                pdf.close()
                return n_pages, pages_b64

            n_pages, pages_b64 = await asyncio.to_thread(_render_pages)
        except Exception as e:
            return f"❌ Gagal render PDF: {e}"

        def _page_bar(done: int, total: int, w: int = 16) -> str:
            n = int(w * done / max(total, 1))
            return "█" * n + "░" * (w - n)

        analyses   = []
        done_pages = []
        total_pages_to_read = len(pages_b64)

        for i, b64 in enumerate(pages_b64, 1):
            # Progress update sebelum analisis halaman ini
            if on_progress:
                bar = _page_bar(i - 1, total_pages_to_read)
                pct = int(100 * (i - 1) / total_pages_to_read)
                done_str = ", ".join(str(p) for p in done_pages[-5:])
                done_hint = f"  ✅ Hal {done_str}\n" if done_pages else ""
                await on_progress(
                    f"📸 *MEMBACA PDF VIA VISION AI*\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"📄 `{file_path.name}`\n"
                    f"_{n_pages} halaman total_\n\n"
                    f"`[{bar}]` {pct}%\n"
                    f"🔄 Halaman {i}/{total_pages_to_read} — menganalisis...\n\n"
                    f"{done_hint}"
                )

            vision_msg = {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": "image/jpeg", "data": b64},
                    },
                    {
                        "type": "text",
                        "text": (
                            f"Ekstrak dan tulis ulang SEMUA teks dari halaman {i} PDF ini. "
                            "Pertahankan heading, sub-heading, bullet point, dan tabel. "
                            "Jangan skip konten apapun. Bahasa: ikuti bahasa dokumen."
                        ),
                    },
                ],
            }
            try:
                text, _ = await router.call(
                    messages=[vision_msg],
                    temperature=0.3,
                    max_tokens=2048,
                )
                analyses.append(f"=== Halaman {i}/{n_pages} ===\n{text}")
                done_pages.append(i)
            except Exception as e:
                analyses.append(f"=== Halaman {i}/{n_pages} === [Vision error: {e}]")
                done_pages.append(i)

        # Progress: selesai semua halaman
        if on_progress:
            bar = _page_bar(total_pages_to_read, total_pages_to_read)
            await on_progress(
                f"📸 *MEMBACA PDF VIA VISION AI*\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"📄 `{file_path.name}`\n\n"
                f"`[{bar}]` 100%\n"
                f"✅ Semua {total_pages_to_read} halaman selesai dibaca!\n\n"
                f"✨ Menyusun resume..."
            )

        combined = "\n\n".join(analyses)
        return (
            f"📄 **{file_path.name}** (PDF scan, {n_pages} hal — dibaca via Vision AI)\n"
            f"Diekstrak: {len(pages_b64)} dari {n_pages} halaman\n\n"
            f"---\n{combined}"
        )

    def _write_file(self, path: str, content: str) -> str:
        safe_path = PROJECT_ROOT / path.lstrip("/").lstrip("\\")
        safe_path.parent.mkdir(parents=True, exist_ok=True)
        safe_path.write_text(content, encoding="utf-8")
        return f"✅ File disimpan: {path} ({len(content)} karakter)"

    def _remember(self, fact: str, category: str = "project") -> str:
        MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        existing = MEMORY_FILE.read_text(encoding="utf-8") if MEMORY_FILE.exists() else "# Hermes Memory\n\n"
        from datetime import datetime
        entry = f"- **[{category.upper()}]** {fact}  _(saved: {datetime.now().strftime('%Y-%m-%d %H:%M')})_\n"
        MEMORY_FILE.write_text(existing + entry, encoding="utf-8")
        return f"✅ Tersimpan ke memori: {fact[:80]}..."

    async def _run_python(self, code: str) -> str:
        result = await execute_python(code, timeout=20)
        if "error" in result:
            return f"❌ Error: {result['error']}"
        out = result.get("stdout", "").strip()
        err = result.get("stderr", "").strip()
        parts = []
        if out:
            parts.append(f"Output:\n{out[:2000]}")
        if err:
            parts.append(f"Stderr:\n{err[:500]}")
        return "\n".join(parts) if parts else "✅ Selesai (tidak ada output)"

    def _create_skill(self, name: str, description: str, content: str) -> str:
        skills_dir = PROJECT_ROOT / "data" / "skills"
        skills_dir.mkdir(parents=True, exist_ok=True)
        skill_file = skills_dir / f"{name}.md"
        skill_content = f"""# Skill: {name}
**Deskripsi:** {description}

---

{content}

---
*Skill dibuat oleh Hermes Agent pada bot Reflective Koala ATG*
"""
        skill_file.write_text(skill_content, encoding="utf-8")
        return f"✅ Skill '{name}' berhasil dibuat: {skill_file.relative_to(PROJECT_ROOT)}"


def load_memory() -> str:
    """Baca isi memori Hermes."""
    if not MEMORY_FILE.exists():
        return ""
    return MEMORY_FILE.read_text(encoding="utf-8")


def load_skills_context() -> str:
    """
    Baca semua skill yang tersedia:
      - data/skills/          → skill lokal buatan bot
      - data/hermes_skills/   → skill dari NousResearch/hermes-agent
      - data/claude_skills/   → skill dari alirezarezvani/claude-skills (338 skill)
    """
    skills = []

    # Local & Hermes skills (flat directories)
    for skills_dir, label in [
        (PROJECT_ROOT / "data" / "skills",       "Local"),
        (PROJECT_ROOT / "data" / "hermes_skills", "Hermes"),
    ]:
        if not skills_dir.exists():
            continue
        for f in sorted(skills_dir.glob("*.md")):
            try:
                content = f.read_text(encoding="utf-8")
                skills.append(f"--- Skill [{label}]: {f.stem} ---\n{content[:1200]}")
            except Exception:
                pass

    # Claude skills (subdirectories per domain)
    claude_root = PROJECT_ROOT / "data" / "claude_skills"
    if claude_root.exists():
        for domain_dir in sorted(claude_root.iterdir()):
            if not domain_dir.is_dir():
                continue
            for f in sorted(domain_dir.glob("*.md")):
                try:
                    content = f.read_text(encoding="utf-8")
                    # Hanya ambil 800 char per skill agar tidak terlalu panjang
                    skills.append(
                        f"--- Claude Skill [{domain_dir.name}]: {f.stem} ---\n{content[:800]}"
                    )
                except Exception:
                    pass

    return "\n\n".join(skills)
