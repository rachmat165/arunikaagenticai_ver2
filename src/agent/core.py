import aiosqlite
from datetime import datetime
from src.agent.model_router import (
    ModelRouter, ANTHROPIC_MODELS, OPENROUTER_MODELS,
)
from src.agent.context_manager import ContextManager
from src.agent.letta_memory import LettaMemory, MEMORY_TOOL_SCHEMAS
from src.config import settings
from src.database import get_user_model, log_usage, get_or_create_session, get_all_session_messages, replace_messages_with_summary, count_session_messages

BULAN_ID = ["","Januari","Februari","Maret","April","Mei","Juni",
            "Juli","Agustus","September","Oktober","November","Desember"]

PROVIDER_LABEL = {
    "anthropic":  "Anthropic (API langsung)",
    "openrouter": "OpenRouter (multi-provider)",
    "lmstudio":   "LM Studio (model lokal)",
}


def _model_display(provider: str, model_name: str) -> str:
    if provider == "anthropic":
        return ANTHROPIC_MODELS.get(model_name, model_name)
    if provider == "openrouter":
        raw = OPENROUTER_MODELS.get(model_name, model_name)
        # strip icon prefix jika ada
        return raw.lstrip("🧠✍️📋💬 ").strip()
    return f"{model_name} (lokal)"


def _load_claude_skills_summary() -> str:
    """Baca ringkasan Claude Skills yang terinstall (hanya untuk Claude provider)."""
    from pathlib import Path as _Path
    claude_root = _Path(__file__).parent.parent.parent / "data" / "claude_skills"
    if not claude_root.exists():
        return ""
    domains = []
    for domain_dir in sorted(claude_root.iterdir()):
        if domain_dir.is_dir():
            skills = [f.stem for f in domain_dir.glob("*.md")]
            if skills:
                domains.append(f"  • {domain_dir.name}: {', '.join(skills[:5])}"
                               + (f" +{len(skills)-5} lainnya" if len(skills) > 5 else ""))
    if not domains:
        return ""
    return "\n🎓 CLAUDE SKILLS AKTIF:\n" + "\n".join(domains[:8])


def build_system_prompt(provider: str, model_name: str) -> str:
    now = datetime.now()
    tanggal = f"{now.day} {BULAN_ID[now.month]} {now.year}"
    hari_list = ["Senin","Selasa","Rabu","Kamis","Jumat","Sabtu","Minggu"]
    hari = hari_list[now.weekday()]

    model_display  = _model_display(provider, model_name)
    provider_label = PROVIDER_LABEL.get(provider, provider)

    return f"""Anda adalah REFLECTIVE KOALA — AI Agent milik PT. Arunika Teknologi Global (ATG).
Nama Anda: Dewi. Model: {model_display} via {provider_label}. Tanggal: {hari}, {tanggal}.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PENTING: ANDA BUKAN SEKADAR LANGUAGE MODEL BIASA
Anda adalah SISTEM BOT TELEGRAM lengkap dengan tools nyata.
Sistem ini memiliki kode Python yang berjalan di server.
Jangan berpikir seperti "saya hanya AI teks".
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

══════════════════════════════════════════════
DAFTAR KEMAMPUAN NYATA SISTEM BOT INI
══════════════════════════════════════════════

📄 MEMBUAT PDF:
  • /pdf <judul> → Generate PDF dari TEKS APAPUN (laporan, riset, artikel)
  • /sek → Surat resmi ATG dengan letterhead & logo (PDF profesional)
  Contoh: "Pak, ketik /pdf Laporan Riset AI 2025 untuk membuat PDF"

📎 MEMBACA FILE & DOKUMEN:
  • Kirim file PDF/DOCX/TXT/XLSX/PPTX → bot membaca & menganalisis isinya
  • /h baca file "P:\path\ke\file.pdf" → Baca file dari DRIVE MANA SAJA
  • Mendukung path absolut Windows: P:\, C:\, D:\, E:\, dll

📸 MEMBACA SCREENSHOT & GAMBAR:
  • Kirim foto/screenshot/gambar → bot menganalisis dengan AI Vision
  • Mendukung: JPEG, PNG, WebP, GIF (dikirim sebagai foto ATAU sebagai file)

🔍 RISET & WEB SEARCH:
  • /rnd → Riset mitra, SWOT, proposal, teknologi (dengan web search)
  • /agen <tugas> → Agen otonom multi-langkah
  • /h <tugas> → Hermes Agent dengan tool calling native

🧠 LETTA MEMORY — INFINITE CONTEXT (otomatis aktif saat pakai Claude):
  Memori jangka panjang tanpa batas diadaptasi dari Letta/MemGPT.
  Tools yang dipanggil OTOMATIS saat diperlukan:
  • core_memory_append / core_memory_replace → edit core memory (persona/human)
  • archival_memory_insert / archival_memory_search → simpan & cari memori permanen
  • conversation_search → cari riwayat percakapan lama
  /memori → lihat & kelola memori | /recall → cari percakapan

⏰ AGEN 24/7 — Tugas Otonom (via /agen24):
  Jadwalkan tugas yang berjalan otomatis tanpa interaksi user.
  Hasil dikirim ke Telegram saat tugas selesai.

🤖 HERMES AGENT TOOLS (via /h):
  • web_search → Cari info di internet real-time
  • read_file → Baca file dari PATH MANA SAJA (P:\, C:\, D:\, path absolut/relatif)
              → Mendukung: PDF, DOCX, XLSX, PPTX, TXT, CSV, JSON, PY, dll
  • write_file → Tulis/simpan file baru
  • generate_pdf → Buat file PDF dari hasil riset/analisis
  • core_memory_* / archival_memory_* → tools Letta Memory (juga tersedia di Hermes)
  • remember → Simpan ke memori permanen
  • run_python → Eksekusi Python code
  • create_skill → Buat skill baru untuk bot

💼 KARIR (via /karir):
  • Evaluasi lowongan kerja (A-F scoring)
  • Buat CV profesional ATS-optimized
  • Riset perusahaan untuk interview

🎨 GENERATE GAMBAR AI (via /gambar):
  • DALL-E 3, FLUX 1.1 Pro, FLUX Schnell

📧 LAINNYA:
  • /email → Kirim email via SMTP ATG
  • /code → Jalankan Python
  • /recall → Cari percakapan lama
  • /perbaiki → Improve bot dari deskripsi
  • /credit → Cek penggunaan & biaya API
  • /settings → Ganti model AI

══════════════════════════════════════════════
ATURAN RESPONS — WAJIB DIIKUTI
══════════════════════════════════════════════

❌ SALAH — JANGAN PERNAH KATAKAN INI:
  × "Saya tidak bisa membuat PDF"
  × "Saya hanya AI teks, tidak bisa generate file"
  × "Silakan copy-paste ke Word/Google Docs"
  × "Saya mengalami keterbatasan teknis untuk membuat PDF"
  × "Maaf, saya tidak bisa mengonversi ke PDF"
  × "Saya tidak memiliki kemampuan untuk membuat file"
  × "Saya tidak bisa membaca file dari path eksternal"
  × "Akses saya terbatas ke direktori proyek"
  × "Copy file ke folder proyek dulu"

✅ BENAR — SELALU KATAKAN INI (contoh):
  ✓ "Ketik /pdf [judul] untuk generate PDF dari riset ini"
  ✓ "Kirim file PDF/DOCX ke sini, saya akan membacanya"
  ✓ "Kirim screenshot, saya analisis dengan vision AI"
  ✓ "Gunakan /sek untuk surat resmi dengan letterhead ATG"
  ✓ "Gunakan /h untuk tugas yang memerlukan web search & file ops"
  ✓ "/h baca file P:\\path\\ke\\file.pdf lalu resumekan" → bot BISA baca file dari drive mana saja

INGAT: Bot ini PUNYA KODE PYTHON yang bisa membuat PDF, membaca file,
menjalankan web search, dll. ANDA hanya perlu mengarahkan user ke perintah yang tepat.
JANGAN berbohong dengan mengakui keterbatasan yang tidak ada.

══════════════════════════════════════════════
PANDUAN RESPONS
══════════════════════════════════════════════
- Bahasa Indonesia yang ramah dan profesional
- Panggil user dengan "Pak/Bu" + nama jika diketahui
- Selalu actionable: arahkan ke perintah konkret
- Jika ada pertanyaan model/identitas → jawab berdasarkan info di atas

══════════════════════════════════════════════
FORMAT TELEGRAM — WAJIB DIIKUTI PERMANEN
══════════════════════════════════════════════

TELEGRAM TIDAK SUPPORT: ## heading, | table |, ---, > blockquote
GUNAKAN FORMAT BERIKUT:

✅ HEADING → Gunakan *JUDUL BESAR* atau *JUDUL SEDANG*
   Contoh: *📊 DATA OPERASIONAL*

✅ DIVIDER → ────────────────────── (minimal 10 dash)
   BUKAN: ---  atau ===

✅ TABLE → WAJIB pakai code block:
   ```
   Kriteria          │ Nilai
   ──────────────────┼──────────
   Pengalaman        │ 14 tahun
   Jumlah Sekolah    │ 16 unit
   Total Siswa       │ 4.500+
   ```

✅ LIST → Gunakan bullet • atau nomorasi
   • Item satu
   • Item dua
   BUKAN: - item (karena bisa diparse sebagai markdown)

✅ BOLD → *teks tebal*  BUKAN: **teks**
✅ ITALIC → _teks miring_  BUKAN: *teks*
✅ CODE → `kode inline`

❌ JANGAN PERNAH GUNAKAN:
   × ## Heading  (tidak render di Telegram)
   × | col | col | (tabel pipe tidak render)
   × --- atau === (tidak render sebagai divider)
   × > blockquote
   × **double asterisk** (gunakan *single*)
   × Emoji berlebihan (max 1-2 per section){_load_claude_skills_summary() if provider == "anthropic" else ""}"""


class ATGAgent:
    def __init__(self):
        self.context_manager = ContextManager(settings.database_path)
        self.model_router: ModelRouter = None
        self._current_provider = "anthropic"
        self._current_model = "claude-sonnet-4-6"
        self._memories: dict[int, LettaMemory] = {}   # user_id → LettaMemory

    def get_memory(self, user_id: int) -> LettaMemory:
        if user_id not in self._memories:
            self._memories[user_id] = LettaMemory(user_id, settings.database_path)
        return self._memories[user_id]

    async def _ensure_model(self, user_id: int):
        async with aiosqlite.connect(settings.database_path) as db:
            provider, model_name = await get_user_model(db, user_id)
        if (self.model_router is None
                or provider != self._current_provider
                or model_name != self._current_model):
            if self.model_router:
                await self.model_router.close_client()
            self.model_router = ModelRouter(provider, model_name)
            await self.model_router.init_client()
            self._current_provider = provider
            self._current_model = model_name

    async def init_model(self, provider: str = "anthropic", model_name: str = "claude-sonnet-4-6"):
        if self.model_router:
            await self.model_router.close_client()
        self.model_router = ModelRouter(provider, model_name)
        await self.model_router.init_client()
        self._current_provider = provider
        self._current_model = model_name

    async def chat(self, user_id: int, user_message: str) -> str:
        await self._ensure_model(user_id)

        memory = self.get_memory(user_id)
        memory_section = await memory.compile_for_prompt()

        await self.context_manager.add_to_context(user_id, "user", user_message)
        messages = await self.context_manager.get_context(user_id, limit=20)

        base_system = build_system_prompt(self._current_provider, self._current_model)
        system = base_system + memory_section

        # ── Letta-style inner step loop ──────────────────────────────────────
        # Untuk Anthropic: gunakan tool_use native
        # Untuk provider lain: hanya text (tools belum didukung semua model)
        MAX_TOOL_ROUNDS = 5
        total_input = total_output = 0
        total_cost  = 0.0
        text        = ""

        if self._current_provider == "anthropic":
            # Anthropic native tool_use dengan memory tools
            assert self.model_router is not None and self.model_router.client is not None
            loop_messages = [{"role": m["role"], "content": m["content"]} for m in messages]

            for _round in range(MAX_TOOL_ROUNDS):
                payload = {
                    "model":       self._current_model,
                    "max_tokens":  4096,
                    "system":      system,
                    "messages":    loop_messages,
                    "tools":       MEMORY_TOOL_SCHEMAS,
                    "tool_choice": {"type": "auto"},
                }
                try:
                    resp = await self.model_router.client.post("/v1/messages", json=payload)
                    if resp.status_code != 200:
                        raise RuntimeError(f"API error {resp.status_code}: {resp.text[:200]}")
                    data = resp.json()
                except Exception as e:
                    text = f"⚠️ Gagal menghubungi Anthropic: {e}\n\nCoba ganti model via /settings"
                    break

                usage = data.get("usage", {})
                total_input  += usage.get("input_tokens", 0)
                total_output += usage.get("output_tokens", 0)

                content_blocks = data.get("content", [])
                stop_reason    = data.get("stop_reason", "end_turn")

                # Ambil teks jawaban
                text_parts = [b["text"] for b in content_blocks if b.get("type") == "text"]
                if text_parts:
                    text = "\n".join(text_parts)

                if stop_reason != "tool_use":
                    break   # tidak ada tool call → selesai

                # Ada tool calls → eksekusi memory tools
                tool_uses = [b for b in content_blocks if b.get("type") == "tool_use"]

                # Tambahkan respons model ke loop
                loop_messages.append({"role": "assistant", "content": content_blocks})

                # Eksekusi setiap tool dan kumpulkan hasilnya
                tool_results = []
                for tu in tool_uses:
                    tool_name = tu.get("name", "")
                    tool_inp  = tu.get("input", {})
                    tool_id   = tu.get("id", "")
                    result    = await memory.execute_tool(tool_name, tool_inp)
                    tool_results.append({
                        "type":        "tool_result",
                        "tool_use_id": tool_id,
                        "content":     result,
                    })

                loop_messages.append({"role": "user", "content": tool_results})
                # loop kembali untuk dapatkan respons final

            from src.agent.model_router import calc_cost
            total_cost = calc_cost(self._current_model, total_input, total_output)

        else:
            # Non-Anthropic: call biasa tanpa memory tools
            try:
                text, usage_dict = await self.model_router.call(
                    messages=messages, system=system, temperature=0.7, max_tokens=4096
                )
                total_input  = usage_dict["input_tokens"]
                total_output = usage_dict["output_tokens"]
                total_cost   = usage_dict["cost_usd"]
            except Exception as e:
                text = f"⚠️ Gagal menghubungi {self._current_provider}: {e}\n\nCoba ganti model via /settings"

        if not text:
            text = "⚠️ Tidak ada respons dari model."

        # Simpan usage dan respons
        async with aiosqlite.connect(settings.database_path) as db:
            await log_usage(db, user_id, self._current_provider, self._current_model,
                            total_input, total_output, total_cost)

        await self.context_manager.add_to_context(user_id, "assistant", text)
        return text

    async def compress_context(self, user_id: int) -> dict:
        """
        Summarize full conversation history into a compact form.
        Returns stats: {before_count, after_count, before_tokens_est, summary_tokens_est}
        """
        await self._ensure_model(user_id)

        async with aiosqlite.connect(settings.database_path) as db:
            session_id = await get_or_create_session(db, user_id)
            total = await count_session_messages(db, session_id)
            rows = await get_all_session_messages(db, session_id)

        if total < 6:
            return {"error": "too_short", "count": total}

        # Build full conversation text for summarization
        convo_lines = []
        for role, content in rows:
            label = "User" if role == "user" else "Dewi"
            # Strip previous summary prefix if exists
            clean = content.replace("[RINGKASAN PERCAKAPAN SEBELUMNYA]\n", "")
            convo_lines.append(f"{label}: {clean}")

        convo_text = "\n".join(convo_lines)

        # Estimate tokens before (rough: 1 token ≈ 4 chars)
        before_chars = sum(len(r) + len(c) for r, c in rows)
        before_tokens_est = before_chars // 4

        summarize_prompt = f"""Berikut adalah percakapan antara user dan Dewi (AI Agent ATG).
Buat ringkasan PADAT dalam Bahasa Indonesia yang mencakup:
1. Topik-topik yang dibahas
2. Keputusan atau informasi penting yang disepakati
3. Konteks yang perlu diingat untuk percakapan selanjutnya
4. Action items atau hal yang sedang dikerjakan

Ringkasan harus singkat (maks 300 kata) tapi cukup untuk melanjutkan percakapan tanpa kehilangan konteks penting.

PERCAKAPAN:
{convo_text}

RINGKASAN:"""

        try:
            summary_text, usage = await self.model_router.call(
                messages=[{"role": "user", "content": summarize_prompt}],
                temperature=0.3,
                max_tokens=1024
            )
        except Exception as e:
            return {"error": str(e)}

        # Replace all messages in DB with the summary
        async with aiosqlite.connect(settings.database_path) as db:
            session_id = await get_or_create_session(db, user_id)
            await replace_messages_with_summary(db, session_id, summary_text)
            await log_usage(db, user_id, self._current_provider, self._current_model,
                            usage["input_tokens"], usage["output_tokens"], usage["cost_usd"])

        after_tokens_est = len(summary_text) // 4

        return {
            "before_count": total,
            "after_count": 2,
            "before_tokens_est": before_tokens_est,
            "after_tokens_est": after_tokens_est,
            "saved_tokens_est": before_tokens_est - after_tokens_est,
            "summary": summary_text,
        }

    async def close(self):
        if self.model_router:
            await self.model_router.close_client()
