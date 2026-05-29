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

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
MEMORY_FILE  = PROJECT_ROOT / "data" / "hermes_memory.md"

# ── Tool schemas (format Anthropic — dikonversi ke OpenAI oleh model_router) ──

TOOL_SCHEMAS = [
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
        "description": "Baca isi file dari proyek bot. Gunakan untuk membaca kode, config, atau dokumen internal.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "path file relatif dari root proyek (contoh: src/config.py)"
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
]


class ToolExecutor:
    def __init__(self):
        self._fc = (
            FirecrawlClient(settings.firecrawl_api_key)
            if settings.firecrawl_api_key else None
        )

    async def execute(self, tool_name: str, tool_input: dict) -> str:
        """Eksekusi satu tool call. Return string hasil."""
        try:
            if tool_name == "web_search":
                return await self._web_search(**tool_input)
            elif tool_name == "read_file":
                return self._read_file(**tool_input)
            elif tool_name == "write_file":
                return self._write_file(**tool_input)
            elif tool_name == "remember":
                return self._remember(**tool_input)
            elif tool_name == "run_python":
                return await self._run_python(**tool_input)
            elif tool_name == "create_skill":
                return self._create_skill(**tool_input)
            else:
                return f"❌ Tool '{tool_name}' tidak dikenal."
        except Exception as e:
            logger.exception("Tool %s error: %s", tool_name, e)
            return f"❌ Error menjalankan tool {tool_name}: {e}"

    async def _web_search(self, query: str, limit: int = 3) -> str:
        if not self._fc:
            return "❌ Firecrawl tidak dikonfigurasi. Set FIRECRAWL_API_KEY di .env"
        results = await self._fc.search(query, limit=min(limit, 5))
        if not results:
            return f"Tidak ada hasil untuk: {query}"
        return self._fc.format_search_results(results, max_chars_each=2000)

    def _read_file(self, path: str) -> str:
        safe_path = PROJECT_ROOT / path.lstrip("/").lstrip("\\")
        if not safe_path.exists():
            return f"❌ File tidak ditemukan: {path}"
        if safe_path.stat().st_size > 50_000:
            return f"❌ File terlalu besar (>{50_000} bytes): {path}"
        try:
            return safe_path.read_text(encoding="utf-8")
        except Exception as e:
            return f"❌ Gagal membaca {path}: {e}"

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
    """Baca semua skill yang tersedia sebagai konteks sistem."""
    skills_dir = PROJECT_ROOT / "data" / "skills"
    if not skills_dir.exists():
        return ""
    skills = []
    for f in skills_dir.glob("*.md"):
        try:
            content = f.read_text(encoding="utf-8")
            skills.append(f"--- Skill: {f.stem} ---\n{content[:1500]}")
        except Exception:
            pass
    return "\n\n".join(skills)
