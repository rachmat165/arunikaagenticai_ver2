from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from src.auth import check_user_allowed
from src.agent import ATGAgent, ANTHROPIC_MODELS, OPENROUTER_MODELS, OPENROUTER_MODEL_GROUPS, fetch_anthropic_models, fetch_lmstudio_models
from src.agent.model_router import OPENROUTER_IMAGE_MODELS, generate_image_openrouter
from src.database import set_user_model, get_user_model, get_user_usage, get_usage_by_model
from src.config import settings
from src.modules.rnd import RndHandler
from src.modules.karir import KarirHandler
from src.modules.agen import AgenHandler
from src.modules.hermes import HermesHandler
from src.agent.agent24 import Agent24Runner, create_task, list_tasks, cancel_task
from src.tools.email_sender import send_email, test_smtp_connection
from src.tools.surat_generator import SuratGenerator
from src.tools.code_executor import execute_python, apply_improvement, restart_bot
from src.tools.api_balance import check_openrouter_balance, check_anthropic_balance, IDR_RATE
from src.tools.file_reader import extract_text, is_image, is_supported
from src.tools.general_pdf import generate_document_pdf_async
import aiosqlite
import logging
import asyncio
from datetime import datetime as _dt

logger = logging.getLogger(__name__)

class TelegramGateway:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.agent = ATGAgent()
        self.rnd_module = RndHandler()
        self.karir_module = KarirHandler()
        self.agen_module  = AgenHandler()
        self.hermes       = HermesHandler()
        self.surat_gen    = SuratGenerator(settings.output_dir)

        # ── 24/7 Agent Runner ─────────────────────────────────────────────────
        # Diinisialisasi tapi belum distart; start() dipanggil dari main.py
        # setelah event loop aktif
        self.agent24 = Agent24Runner(
            db_path=db_path,
            agent_runner=self._agent_runner_callback,
            message_sender=self._message_sender_callback,
        )

    async def _agent_runner_callback(self, user_id: int, task_desc: str) -> str:
        """Callback untuk Agent24 — jalankan tugas dengan AI Agent."""
        try:
            # Gunakan ATGAgent untuk menjalankan tugas
            result = await self.agent.chat(
                user_id=user_id,
                user_message=f"Jalankan tugas ini: {task_desc}",
            )
            return str(result) if result else "Tugas selesai tanpa output."
        except Exception as e:
            logger.exception("Agent runner error: %s", e)
            return f"Error menjalankan tugas: {e}"

    async def _message_sender_callback(self, chat_id: int, text: str) -> None:
        """Callback untuk Agent24 — kirim hasil ke Telegram chat."""
        try:
            # Kirim pesan ke chat yang ditentukan
            if hasattr(self, '_app') and self._app:
                await self._app.bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
        except Exception as e:
            logger.exception("Message sender error: %s", e)

    def start_agent24(self, app):
        """Start Agent24 runner. Panggil dari main.py setelah app.start()."""
        self._app = app
        self.agent24.start()
        logger.info("Agent24 runner started successfully")

    def _render_progress_bar(self, current: int, total: int, task_name: str = "", width: int = 20) -> str:
        """Render progress bar untuk long-running tasks."""
        if total <= 0:
            pct = 0
            done = 0
        else:
            pct = int(100 * current / total)
            done = int(width * current / total)

        bar = "█" * done + "░" * (width - done)
        task_str = f"\n💼 _{task_name}_" if task_name else ""
        return f"`[{bar}]` {pct}%  •  Step {current}/{total}{task_str}"

    def _get_presentation_skill_hint(self) -> str:
        """Ambil hint tentang Claude Skills untuk presentasi/PowerPoint."""
        from pathlib import Path as _Path
        skills_root = _Path(__file__).parent.parent.parent / "data" / "claude_skills"

        # Cari skill yang relevan untuk presentasi/PowerPoint
        presentation_skills = []
        if skills_root.exists():
            for domain_dir in skills_root.iterdir():
                if domain_dir.is_dir():
                    domain_name = domain_dir.name.lower()
                    # Cari di domain seperti product-management, marketing, business
                    if any(x in domain_name for x in ["product", "marketing", "business", "presentation"]):
                        skills = [f.stem for f in domain_dir.glob("*.md")]
                        presentation_skills.extend(skills[:3])

        if presentation_skills:
            return f"🎓 _Claude Skills siap membantu: {', '.join(presentation_skills[:5])}_"
        return "🎓 _Claude Skills akan otomatis digunakan untuk membuat presentasi profesional._"

    async def _generate_surat_with_hermes(
        self,
        source_result: str,
        source_title: str,
        template_type: str,
        user_id: int,
        on_progress=None
    ) -> str:
        """Generate surat profesional dengan Hermes Agent + Claude Skills."""
        template_instructions = {
            "proposal": "Buat surat proposal kerjasama yang profesional dan persuasif.",
            "offering": "Buat surat penawaran produk/layanan dengan detail harga dan benefit.",
            "request": "Buat surat permohonan atau undangan yang formal dan sopan.",
            "all": "Buat 3 versi surat: (1) Proposal, (2) Offering, (3) Request dari data ini.",
        }

        prompt = f"""Generate surat profesional dengan template {template_type.upper()}:

{template_instructions.get(template_type, "")}

SUMBER DATA:
{source_result}

JUDUL: {source_title}

INSTRUKSI:
1. Analisis data sumber dan ekstrak poin-poin penting
2. Generate surat dengan struktur profesional:
   - Pembuka (salam + maksud surat)
   - Isi (poin utama, detail, benefit)
   - Penutup (call-to-action, tanda tangan)
3. Gunakan nada formal namun human-friendly
4. Format dengan ATG branding
5. Jika template='all', pisahkan 3 surat dengan header jelas

OUTPUT: Hanya surat jadi (tanpa penjelasan tambahan)."""

        try:
            router = await self._ensure_model_router(user_id)

            async def progress_callback(msg: str):
                if on_progress:
                    await on_progress(f"🎯 {msg}")

            result = await self.hermes.run(
                task=prompt,
                router=router,
                on_progress=progress_callback,
                user_id=user_id,
            )
            return result
        except Exception as e:
            logger.exception("Hermes surat generation error: %s", e)
            raise RuntimeError(f"Gagal generate surat: {e}")

    async def show_result_with_export(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        result_text: str,
        result_type: str = "general",  # research, analysis, rnd, hermes, karir, etc
        title: str = None,
    ):
        """
        Tampilkan hasil + menu konversi otomatis ke berbagai format.

        result_type: 'research', 'analysis', 'rnd', 'hermes', 'karir', 'riset', etc
        """
        if not update.message:
            return

        # Simpan hasil terakhir untuk konversi
        if context.user_data is None:
            context.user_data = {}
        context.user_data["last_result"] = {
            "text": result_text,
            "type": result_type,
            "title": title if title else f"Hasil {result_type}",
            "timestamp": _dt.now().isoformat(),
        }

        # Bagi hasil jika terlalu panjang
        if len(result_text) > 4096:
            for i in range(0, len(result_text), 4096):
                await update.message.reply_text(result_text[i:i+4096], parse_mode="Markdown")
        else:
            await update.message.reply_text(result_text, parse_mode="Markdown")

        # Tampilkan menu konversi
        keyboard = [
            [
                InlineKeyboardButton("📄 Surat", callback_data="export_surat"),
                InlineKeyboardButton("📊 PDF", callback_data="export_pdf"),
            ],
            [
                InlineKeyboardButton("📈 Excel", callback_data="export_excel"),
                InlineKeyboardButton("🎨 Presentasi", callback_data="export_presentasi"),
            ],
            [
                InlineKeyboardButton("📱 Sosmed + Gambar", callback_data="export_sosmed"),
            ],
        ]
        await update.message.reply_text(
            "💾 *Konversi hasil ke format lain:*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id if update.effective_user else None
        print(
            f"[TG_DEBUG] start() called user_id={user_id} text={getattr(update.message,'text',None)!r}",
            flush=True,
        )

        try:
            logger.info("Telegram /start received user_id=%s", user_id)

            if not await check_user_allowed(user_id):
                if update.message:
                    await update.message.reply_text("❌ Anda tidak diizinkan menggunakan bot ini.")
                return

            welcome_text = """👋 Selamat datang di REFLECTIVE KOALA!

AI Agent komprehensif PT. Arunika Teknologi Global.

📋 MENU UTAMA:
• /tools — Lihat SEMUA skill & tools
• /fungsi — Daftar lengkap perintah

📄 DOKUMEN & PDF:
• /pdf <judul> — Generate PDF dari teks apapun
• /sek — Surat resmi ATG (letterhead PDF)
• Kirim file PDF/DOCX/TXT → dibaca AI
• Kirim foto/screenshot → dianalisis Vision AI

🤖 AGEN & RISET:
• /h <tugas> — Hermes Agent (tool calling)
• /agen <tugas> — Agen otonom multi-step
• /rnd — R&D & riset mitra
• /karir — Evaluasi kerja, CV, riset perusahaan

🎨 KREASI:
• /gambar <deskripsi> — Generate gambar AI
• /sosmed — Konten social media
• /email — Kirim email

⚙️ PENGATURAN:
• /settings — Ganti provider & model AI
• /recall — Cari percakapan lama
• /credit — Cek biaya API

Ketik pertanyaan bebas kapan saja! 🤖"""

            if not update.message:
                raise RuntimeError("update.message is None in start() handler")

            await update.message.reply_text(welcome_text)

        except Exception as e:
            logger.exception("Telegram /start failed: %s", str(e))
            if update.message:
                await update.message.reply_text(f"❌ /start error: {type(e).__name__}: {e}")

    async def help_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not await check_user_allowed(user_id):
            return

        help_text = """📚 **BANTUAN**

**Perintah Utama:**
/start - Tampilkan menu utama
/settings - Pilih model AI
/help - Bantuan ini

**Modul Sekretaris** (/sek):
- /sek surat - Buat surat dinas
- /sek presentasi - Buat presentasi
- /sek notulensi - Buat notulensi
- /sek agenda - Set agenda meeting
- /sek reminder - Set reminder

**Modul R&D** (/rnd):
- /rnd riset - Riset mitra potensial
- /rnd swot - Analisis SWOT
- /rnd proposal - Buat proposal

**Modul Social Media** (/sosmed):
- /sosmed konten - Buat konten
- /sosmed analisis - Analisis performa
- /sosmed kalender - Content calendar

**Modul Resources** (/resources):
- /resources upload - Upload dokumen
- /resources search - Cari di knowledge base
- /resources produk - Kelola produk

**Modul Automation** (/auto):
- /auto run - Jalankan script
- /auto cron - Set cron job
- /auto scrape - Web scraping

**Tips:**
- Ketik pesan bebas untuk chatting dengan AI
- Gunakan /settings untuk memilih model AI
- Semua percakapan tersimpan di database"""

        await update.message.reply_text(help_text, parse_mode="Markdown")

    async def settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not await check_user_allowed(user_id):
            return

        keyboard = [
            [InlineKeyboardButton("🤖 Anthropic Claude", callback_data="provider_anthropic")],
            [InlineKeyboardButton("🌐 OpenRouter", callback_data="provider_openrouter")],
            [InlineKeyboardButton("🖥️ LM Studio (Lokal)", callback_data="provider_lmstudio")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Pilih provider AI:", reply_markup=reply_markup)

    async def provider_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        user_id = query.from_user.id
        provider = query.data.split("_")[1]
        context.user_data["selected_provider"] = provider

        if provider == "lmstudio":
            await query.edit_message_text("⏳ Mengambil model dari LM Studio lokal...")
            lmstudio_url = getattr(settings, "lmstudio_base_url", "http://localhost:1234")
            lms_models = await fetch_lmstudio_models(lmstudio_url)
            if not lms_models:
                await query.edit_message_text(
                    "❌ *LM Studio tidak terdeteksi!*\n\n"
                    "Pastikan:\n"
                    "1. LM Studio sudah diinstall & dibuka\n"
                    "2. Klik tab *Local Server* → *Start Server*\n"
                    "3. Server berjalan di `http://localhost:1234`\n\n"
                    "Setelah server aktif, coba lagi /settings",
                    parse_mode="Markdown"
                )
                return
            keyboard = [
                [InlineKeyboardButton(f"🖥️ {mid}", callback_data=f"model_{mid}")]
                for mid, _ in lms_models
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text("🖥️ Pilih model LM Studio:", reply_markup=reply_markup)

        elif provider == "anthropic":
            keyboard = [
                [InlineKeyboardButton(display, callback_data=f"model_{model}")]
                for model, display in ANTHROPIC_MODELS.items()
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text("🤖 Pilih model Anthropic:", reply_markup=reply_markup)

        else:
            # OpenRouter — tampilkan grup dahulu
            keyboard = [
                [InlineKeyboardButton(grp["label"], callback_data=f"orgroup_{key}")]
                for key, grp in OPENROUTER_MODEL_GROUPS.items()
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "🌐 *OpenRouter* — Pilih kategori model:",
                reply_markup=reply_markup,
                parse_mode="Markdown",
            )

    async def orgroup_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Tampilkan daftar model untuk satu grup OpenRouter."""
        query = update.callback_query
        if not query or not query.data:
            return
        await query.answer()

        group_key = query.data.split("orgroup_", 1)[1]
        grp = OPENROUTER_MODEL_GROUPS.get(group_key)
        if not grp:
            await query.edit_message_text("❌ Grup tidak ditemukan.")
            return

        keyboard = [
            [InlineKeyboardButton(display, callback_data=f"model_{model_id}")]
            for model_id, display in grp["models"].items()
        ]
        keyboard.append([InlineKeyboardButton("◀️ Kembali ke Kategori", callback_data="provider_openrouter")])

        await query.edit_message_text(
            f"🌐 OpenRouter › {grp['label']}\n\nPilih model:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    async def model_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        user_id = query.from_user.id
        model_name = query.data.split("_", 1)[1]
        provider = context.user_data.get("selected_provider", "anthropic")

        async with aiosqlite.connect(self.db_path) as db:
            await set_user_model(db, user_id, provider, model_name)

        try:
            await self.agent.init_model(provider, model_name)
        except Exception as e:
            await query.edit_message_text(
                f"❌ Gagal mengaktifkan model.\n\nProvider: {provider}\nModel: {model_name}\n\nError: {str(e)}"
            )
            return

        display = (
            (ANTHROPIC_MODELS.get(model_name) if provider == "anthropic" else None)
            or (OPENROUTER_MODELS.get(model_name) if provider == "openrouter" else None)
            or (f"🖥️ {model_name} (Lokal)" if provider == "lmstudio" else f"🖥️ {model_name}")
        )
        await query.edit_message_text(f"✅ Model diatur ke: {display}")

    # ── Context-aware helper ─────────────────────────────────────────────
    async def _get_research_context(
        self, user_id: int, query: str, limit_chars: int = 3000, max_chunks: int = 2,
    ) -> str:
        """Cari pesan AI sebelumnya yang relevan dengan query.

        Dipakai oleh surat / proposal / presentasi agar merujuk hasil riset
        yang sudah dibuat sebelumnya, bukan generate dari nol.
        """
        import re as _re_kw
        try:
            ctx_msgs = await self.agent.context_manager.get_context(user_id, limit=20)
        except Exception as _e:
            logger.warning("Gagal ambil context riset: %s", _e)
            return ""

        STOPWORDS = {
            "surat", "untuk", "utk", "buat", "buatkan", "bikin", "kepada",
            "dari", "yth", "yang", "dengan", "tentang", "perihal", "draft",
            "penawaran", "permohonan", "undangan", "kerjasama", "kolaborasi",
            "proposal", "presentasi", "presentation", "slide", "deck",
            "bahan", "materi", "outline", "tolong", "minta", "saya", "kami",
            "anda", "akan", "harus", "wajib", "dan", "atau", "tapi",
            "ke", "di", "pada", "ini", "itu", "dia", "pdf", "doc", "docx",
            "the", "for", "and", "with", "about",
        }
        keywords = [
            w.lower()
            for w in _re_kw.findall(r"[A-Za-z][A-Za-z0-9'\-]{2,}", query or "")
            if w.lower() not in STOPWORDS
        ]

        relevant: list[str] = []
        for m in ctx_msgs:
            if m.get("role") != "assistant":
                continue
            body = str(m.get("content", ""))
            if len(body) < 200:
                continue
            low = body.lower()
            if not keywords or any(k in low for k in keywords):
                relevant.append(body)

        relevant = relevant[-max_chunks:]
        if not relevant:
            return ""
        return "\n\n──────\n\n".join(relevant)[:limit_chars]

    # ── Telegram formatting helpers ──────────────────────────────────────
    @staticmethod
    def _md_table_to_telegram(table_lines: list[str]) -> str:
        """Convert markdown pipe table into mobile-friendly Telegram format.

        Narrow tables (≤2 cols, total width ≤40) → monospace code block.
        Wider tables → vertical card layout per row (better on mobile).
        """
        import re as _re
        rows: list[list[str]] = []
        for ln in table_lines:
            if _re.match(r"^\s*\|?[\s\-:|]+\|[\s\-:|]+\s*$", ln):
                continue  # separator row
            if "|" not in ln:
                continue
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            rows.append(cells)
        if len(rows) < 2:
            return "\n".join(table_lines)

        header, body = rows[0], rows[1:]
        ncols = max(len(r) for r in rows)
        header = header + [""] * (ncols - len(header))
        body = [r + [""] * (ncols - len(r)) for r in body]
        widths = [max(len(r[i]) for r in [header] + body) for i in range(ncols)]
        total_width = sum(widths) + 3 * (ncols - 1)

        if ncols <= 2 and total_width <= 40:
            out = ["```"]
            out.append(" │ ".join(header[i].ljust(widths[i]) for i in range(ncols)))
            out.append("─┼─".join("─" * widths[i] for i in range(ncols)))
            for r in body:
                out.append(" │ ".join(r[i].ljust(widths[i]) for i in range(ncols)))
            out.append("```")
            return "\n".join(out)

        # Vertical card layout (mobile-friendly)
        out = []
        for r in body:
            out.append("──────────────────────")
            for i, cell in enumerate(r):
                label = header[i] if i < len(header) and header[i] else f"Kolom {i+1}"
                out.append(f"• *{label}:* {cell}")
        out.append("──────────────────────")
        return "\n".join(out)

    def _sanitize_for_telegram(self, text: str) -> str:
        """Bersihkan output AI agar render rapi & profesional di Telegram.

        - `## heading` → `*HEADING*`
        - `**bold**` → `*bold*`
        - `---` / `===` → unicode divider
        - `| col | col |` markdown tables → code block atau vertical cards
        - `> blockquote` → `┃ prefix`
        Konten di dalam ``` ``` code block tidak diubah.
        """
        import re as _re
        if not text:
            return text

        # Lindungi code block triple-backtick
        code_blocks: list[str] = []
        def _stash(m):
            code_blocks.append(m.group(0))
            return f"\x00CB{len(code_blocks)-1}\x00"
        text = _re.sub(r"```[\s\S]*?```", _stash, text)

        # 1) Pipe tables → code block / vertical
        lines = text.split("\n")
        out_lines: list[str] = []
        i = 0
        while i < len(lines):
            line = lines[i]
            is_table_header = (
                line.count("|") >= 2
                and i + 1 < len(lines)
                and _re.match(r"^\s*\|?[\s\-:|]+\|[\s\-:|]+\s*$", lines[i+1])
            )
            if is_table_header:
                tbl = [line]
                j = i + 1
                while j < len(lines) and "|" in lines[j] and lines[j].strip():
                    tbl.append(lines[j])
                    j += 1
                out_lines.append(self._md_table_to_telegram(tbl))
                i = j
            else:
                out_lines.append(line)
                i += 1
        text = "\n".join(out_lines)

        # 2) Headings: ##/###/etc → *UPPER*, # → *Title*
        text = _re.sub(
            r"^#{2,6}\s+(.+?)\s*#*\s*$",
            lambda m: f"*{m.group(1).upper()}*",
            text, flags=_re.MULTILINE,
        )
        text = _re.sub(
            r"^#\s+(.+?)\s*#*\s*$",
            lambda m: f"*{m.group(1)}*",
            text, flags=_re.MULTILINE,
        )

        # 3) Divider --- / === → unicode line
        text = _re.sub(r"^\s*[-=*]{3,}\s*$", "──────────────────────", text, flags=_re.MULTILINE)

        # 4) Double-asterisk bold → single-asterisk
        text = _re.sub(r"\*\*([^\n*]+?)\*\*", r"*\1*", text)

        # 5) Blockquote
        text = _re.sub(r"^>\s+(.+)$", r"┃ \1", text, flags=_re.MULTILINE)

        # Restore code blocks
        for idx, cb in enumerate(code_blocks):
            text = text.replace(f"\x00CB{idx}\x00", cb)
        return text

    async def _send_long(self, update: Update, text: str):
        """Send long text split into Telegram-safe chunks, with sanitization."""
        clean = self._sanitize_for_telegram(text)
        for i in range(0, len(clean), 4096):
            chunk = clean[i:i+4096]
            try:
                await update.message.reply_text(chunk, parse_mode="Markdown")
            except Exception:
                # Fallback: kirim plain bila Markdown parser Telegram nolak chunk
                try:
                    await update.message.reply_text(chunk)
                except Exception as e:
                    logger.warning("Gagal kirim chunk Telegram: %s", e)

    async def _ensure_model_router(self, user_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            provider, model_name = await get_user_model(db, user_id)
        if (not self.agent.model_router
                or self.agent.model_router.provider != provider
                or self.agent.model_router.model_name != model_name):
            await self.agent.init_model(provider, model_name)
        return self.agent.model_router

    async def text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not await check_user_allowed(user_id):
            await update.message.reply_text("❌ Akses ditolak.")
            return

        user_message = update.message.text.strip()
        rnd_state = context.user_data.get("rnd_state")
        logger.info("Telegram text_message received user_id=%s text=%r rnd_state=%r", user_id, user_message, rnd_state)

        # ── R&D state machine ──────────────────────────────────────────────
        if rnd_state:
            await update.message.chat.send_action("typing")
            router = await self._ensure_model_router(user_id)

            # make_progress: tidak lagi digunakan, diganti per-state handler
            pass

            if rnd_state == "riset":
                msg = await update.message.reply_text(
                    f"🔍 *Riset Calon Mitra:* `{user_message}`\n\n"
                    f"{self._render_progress_bar(1, 3, 'Searching web data')}\n\n"
                    "🌐 Mencari informasi via Firecrawl\\.\\.\\.",
                    parse_mode="Markdown"
                )

                step_counter = [1]

                async def progress_riset(text: str):
                    step_counter[0] += 1
                    try:
                        await msg.edit_text(
                            f"🔍 *Riset Calon Mitra:* `{user_message}`\n\n"
                            f"{self._render_progress_bar(min(step_counter[0], 3), 3, text)}\n\n"
                            f"🔄 {text}\\.\\.\\.",
                            parse_mode="Markdown"
                        )
                    except Exception:
                        pass

                result = await self.rnd_module.riset_mitra(user_message, router, on_progress=progress_riset)

                # Show final result dalam progress message
                await msg.edit_text(
                    f"🔍 *Riset Calon Mitra:* `{user_message}`\n\n"
                    f"{self._render_progress_bar(3, 3, 'Complete ✅')}\n\n"
                    "📊 Hasil riset siap di bawah ini:",
                    parse_mode="Markdown"
                )
                await self._send_long(update, result)

            elif rnd_state == "swot":
                msg = await update.message.reply_text(
                    f"📈 *Analisis SWOT:* `{user_message}`\n\n"
                    f"{self._render_progress_bar(1, 3, 'Collecting data')}\n\n"
                    "🔍 Mengumpulkan informasi\\.\\.\\.",
                    parse_mode="Markdown"
                )

                step_counter = [1]

                async def progress_swot(text: str):
                    step_counter[0] += 1
                    try:
                        await msg.edit_text(
                            f"📈 *Analisis SWOT:* `{user_message}`\n\n"
                            f"{self._render_progress_bar(min(step_counter[0], 3), 3, text)}\n\n"
                            f"🔄 {text}\\.\\.\\.",
                            parse_mode="Markdown"
                        )
                    except Exception:
                        pass

                result = await self.rnd_module.analisis_swot(user_message, router, on_progress=progress_swot)

                # Show final result dalam progress message
                await msg.edit_text(
                    f"📈 *Analisis SWOT:* `{user_message}`\n\n"
                    f"{self._render_progress_bar(3, 3, 'Complete ✅')}\n\n"
                    "📊 Hasil analisis siap di bawah ini:",
                    parse_mode="Markdown"
                )
                await self._send_long(update, result)

            elif rnd_state == "proposal_step1":
                context.user_data["rnd_partner"] = user_message
                context.user_data["rnd_state"] = "proposal_step2"
                await update.message.reply_text(
                    f"✅ Mitra: *{user_message}*\n\n"
                    "Jelaskan *jenis proyek/kolaborasi* yang diinginkan:\n"
                    "_Contoh: Pengembangan aplikasi AI, Platform e-learning, Sistem ERP berbasis AI_",
                    parse_mode="Markdown"
                )
                return

            elif rnd_state == "proposal_step2":
                partner = context.user_data.get("rnd_partner", "Mitra")
                msg = await update.message.reply_text(
                    f"📋 *Buat Proposal:* `{partner} × ATG`\n\n"
                    f"{self._render_progress_bar(1, 3, 'Research partner')}\n\n"
                    "🔍 Riset profil mitra\\.\\.\\.",
                    parse_mode="Markdown"
                )

                step_counter = [1]

                async def progress_proposal(text: str):
                    step_counter[0] += 1
                    try:
                        await msg.edit_text(
                            f"📋 *Buat Proposal:* `{partner} × ATG`\n\n"
                            f"{self._render_progress_bar(min(step_counter[0], 3), 3, text)}\n\n"
                            f"🔄 {text}\\.\\.\\.",
                            parse_mode="Markdown"
                        )
                    except Exception:
                        pass

                prior_research = await self._get_research_context(user_id, partner)
                result = await self.rnd_module.buat_proposal(
                    partner, user_message, router,
                    on_progress=progress_proposal,
                    prior_research=prior_research,
                )

                # Show final result dalam progress message
                await msg.edit_text(
                    f"📋 *Buat Proposal:* `{partner} × ATG`\n\n"
                    f"{self._render_progress_bar(3, 3, 'Complete ✅')}\n\n"
                    "📊 Proposal siap di bawah ini:",
                    parse_mode="Markdown"
                )
                await self._send_long(update, result)

            elif rnd_state == "tech":
                msg = await update.message.reply_text(
                    f"🔬 *Riset Teknologi:* `{user_message}`\n\n"
                    f"{self._render_progress_bar(1, 3, 'Searching tech data')}\n\n"
                    "Mencari informasi teknologi terkini...",
                    parse_mode="Markdown"
                )
                step_counter = [1]
                async def progress_tech(text: str):
                    step_counter[0] += 1
                    try:
                        await msg.edit_text(
                            f"🔬 *Riset Teknologi:* `{user_message}`\n\n"
                            f"{self._render_progress_bar(min(step_counter[0], 3), 3, text)}\n\n"
                            f"{text}...",
                            parse_mode="Markdown"
                        )
                    except Exception:
                        pass
                result = await self.rnd_module.riset_teknologi(user_message, router, on_progress=progress_tech)
                await msg.edit_text(
                    f"🔬 *Riset Teknologi:* `{user_message}`\n\n"
                    f"{self._render_progress_bar(3, 3, 'Complete ✅')}\n\n"
                    "Hasil riset siap:",
                    parse_mode="Markdown"
                )
                await self._send_long(update, result)

            elif rnd_state == "scrape":
                url = user_message if user_message.startswith("http") else "https://" + user_message
                msg = await update.message.reply_text(
                    f"🕷️ *Scraping:* `{url}`\n\n"
                    f"{self._render_progress_bar(1, 2, 'Fetching website')}\n\n"
                    "Mengambil konten website...",
                    parse_mode="Markdown"
                )
                step_counter = [1]
                async def progress_scrape(text: str):
                    step_counter[0] += 1
                    try:
                        await msg.edit_text(
                            f"🕷️ *Scraping:* `{url}`\n\n"
                            f"{self._render_progress_bar(min(step_counter[0], 2), 2, text)}\n\n"
                            f"{text}...",
                            parse_mode="Markdown"
                        )
                    except Exception:
                        pass
                result = await self.rnd_module.scrape_website(url, router, on_progress=progress_scrape)
                await msg.edit_text(
                    f"🕷️ *Scraping:* `{url}`\n\n"
                    f"{self._render_progress_bar(2, 2, 'Complete ✅')}\n\n"
                    "Hasil scraping siap:",
                    parse_mode="Markdown"
                )
                await self._send_long(update, result)

            context.user_data.pop("rnd_state", None)
            context.user_data.pop("rnd_partner", None)
            return

        # ── Code REPL state ────────────────────────────────────────────────
        if (context.user_data or {}).get("code_state") == "waiting":
            if context.user_data is not None:
                context.user_data.pop("code_state", None)
            if update.message:
                await self._run_and_reply(update.message, user_message)
            return

        # ── Presentasi state machine ──────────────────────────────────────
        presentasi_state = (context.user_data or {}).get("presentasi_state")
        if presentasi_state:
            await self._handle_presentasi_state(update, context, presentasi_state, user_message)
            return

        # ── Surat state machine ────────────────────────────────────────────
        surat_state = (context.user_data or {}).get("surat_state")
        if surat_state:
            await self._handle_surat_state(update, context, surat_state, user_message)
            return

        # ── Smart Surat Generator state machine ────────────────────────────
        surat_gen_state = (context.user_data or {}).get("surat_gen_state")
        if surat_gen_state:
            await self._handle_surat_gen_state(update, context, surat_gen_state, user_message)
            return

        # ── Surat Email state machine ──────────────────────────────────────
        surat_email_state = (context.user_data or {}).get("surat_email_state")
        if surat_email_state:
            await self._handle_surat_email_state(update, context, surat_email_state, user_message)
            return

        # ── Email state machine ────────────────────────────────────────────
        email_state = (context.user_data or {}).get("email_state")
        if email_state:
            await self._handle_email_state(update, context, email_state, user_message)
            return

        # ── Karir state machine ────────────────────────────────────────────
        karir_state = (context.user_data or {}).get("karir_state")
        if karir_state:
            await self._handle_karir_state(update, context, karir_state, user_message)
            return

        # ── PDF state machine ──────────────────────────────────────────────
        pdf_state = (context.user_data or {}).get("pdf_state")
        if pdf_state:
            await self._handle_pdf_state(update, context, pdf_state, user_message)
            return

        # ── Deteksi "buatkan PDF dari hasil diatas" ────────────────────────
        _pdf_triggers = [
            "buatkan pdf", "jadikan pdf", "buat pdf", "simpan pdf",
            "dalam pdf", "ke pdf", "generate pdf", "cetak pdf",
            "export pdf", "dijadikan pdf", "dibuatkan pdf",
        ]
        if any(t in user_message.lower() for t in _pdf_triggers):
            # Ambil respons AI terakhir dari context untuk dijadikan isi PDF
            ctx_msgs = await self.agent.context_manager.get_context(user_id, limit=15)
            last_ai = next(
                (m["content"] for m in reversed(ctx_msgs)
                 if m.get("role") == "assistant" and len(str(m.get("content", ""))) > 150),
                None,
            )
            if last_ai:
                status = await update.message.reply_text("📄 Membuat PDF dari hasil sebelumnya...")
                try:
                    import re as _re
                    content_str = str(last_ai)
                    # Cari judul dari baris pertama yang bermakna
                    title = "Hasil Analisis ATG"
                    for ln in content_str.split("\n")[:6]:
                        clean = _re.sub(r"[*#`_\[\]]", "", ln).strip()
                        if len(clean) > 12:
                            title = clean[:60]
                            break
                    pdf_path = await generate_document_pdf_async(title, content_str)
                    from pathlib import Path as _Path
                    with open(pdf_path, "rb") as f:
                        await update.message.reply_document(
                            document=f,
                            filename=_Path(pdf_path).name,
                            caption=f"📄 *{title}*\n_PDF dari hasil percakapan — Reflective Koala ATG_",
                            parse_mode="Markdown",
                        )
                    await status.edit_text("📄 PDF selesai dibuat ✅")
                except Exception as e:
                    logger.exception("Auto PDF error: %s", e)
                    await status.edit_text(
                        f"❌ Gagal membuat PDF: {e}\n\n"
                        f"💡 Coba: `/pdf {title}` lalu paste konten secara manual."
                    )
                return

        # ── Normal chat ────────────────────────────────────────────────────
        await update.message.chat.send_action("typing")
        progress_msg = None
        try:
            progress_msg = await update.message.reply_text(
                "🤔 *Dewi sedang berpikir...*\n\n"
                f"{self._render_progress_bar(1, 10, 'Memproses pertanyaan')}\n\n"
                "_Mohon tunggu sebentar..._",
                parse_mode="Markdown",
            )
        except Exception:
            progress_msg = None

        ticker_done = asyncio.Event()
        STEP_LABELS = [
            "Memproses pertanyaan",
            "Menelusuri konteks",
            "Memanggil model AI",
            "Merangkai jawaban",
            "Memformat respons",
            "Menyelesaikan output",
        ]

        async def _tick():
            step = 1
            label_idx = 0
            while not ticker_done.is_set():
                try:
                    await asyncio.wait_for(ticker_done.wait(), timeout=2.0)
                    return
                except asyncio.TimeoutError:
                    pass
                step = min(step + 1, 9)
                label_idx = (label_idx + 1) % len(STEP_LABELS)
                if progress_msg is None:
                    continue
                try:
                    await progress_msg.edit_text(
                        "🤔 *Dewi sedang berpikir...*\n\n"
                        f"{self._render_progress_bar(step, 10, STEP_LABELS[label_idx])}\n\n"
                        "_Mohon tunggu sebentar..._",
                        parse_mode="Markdown",
                    )
                except Exception:
                    pass

        ticker_task = asyncio.create_task(_tick())
        try:
            response = await self.agent.chat(user_id, user_message)
        except Exception as e:
            logger.error(f"Error: {e}")
            ticker_done.set()
            try:
                await ticker_task
            except Exception:
                pass
            if progress_msg is not None:
                try:
                    await progress_msg.edit_text(f"❌ Error: {str(e)}")
                except Exception:
                    await update.message.reply_text(f"❌ Error: {str(e)}")
            else:
                await update.message.reply_text(f"❌ Error: {str(e)}")
            return
        finally:
            ticker_done.set()
            try:
                await ticker_task
            except Exception:
                pass

        if progress_msg is not None:
            try:
                await progress_msg.edit_text(
                    "🤔 *Dewi sedang berpikir...*\n\n"
                    f"{self._render_progress_bar(10, 10, 'Complete ✅')}\n\n"
                    "📨 Jawaban di bawah ini:",
                    parse_mode="Markdown",
                )
            except Exception:
                pass
        await self._send_long(update, response)

    async def sekretaris(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not await check_user_allowed(user_id):
            return

        keyboard = [
            [InlineKeyboardButton("📄 Buat Surat", callback_data="sek_surat")],
            [InlineKeyboardButton("📊 Buat Presentasi", callback_data="sek_presentasi")],
            [InlineKeyboardButton("📝 Notulensi", callback_data="sek_notulensi")],
            [InlineKeyboardButton("📅 Set Agenda", callback_data="sek_agenda")],
            [InlineKeyboardButton("🔔 Set Reminder", callback_data="sek_reminder")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Modul Sekretaris:", reply_markup=reply_markup)

    async def rnd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not await check_user_allowed(user_id):
            return

        # Support direct args: /rnd riset <nama> atau /rnd <free text query>
        args = " ".join(context.args).strip() if context.args else ""
        if args:
            router = await self._ensure_model_router(user_id)
            msg = await update.message.reply_text(
                f"🔍 *Riset:* `{args}`\n\n"
                f"{self._render_progress_bar(1, 3, 'Searching data')}\n\n"
                "🌐 Mencari informasi via Firecrawl\\.\\.\\.",
                parse_mode="Markdown"
            )

            step_counter = [1]

            async def on_progress(text):
                step_counter[0] += 1
                try:
                    await msg.edit_text(
                        f"🔍 *Riset:* `{args}`\n\n"
                        f"{self._render_progress_bar(min(step_counter[0], 3), 3, text)}\n\n"
                        f"🔄 {text}\\.\\.\\.",
                        parse_mode="Markdown"
                    )
                except Exception:
                    pass
            result = await self.rnd_module.riset_mitra(args, router, on_progress=on_progress)

            # Show final result dalam progress message
            await msg.edit_text(
                f"🔍 *Riset:* `{args}`\n\n"
                f"{self._render_progress_bar(3, 3, 'Complete ✅')}\n\n"
                "📊 Hasil riset siap di bawah ini:",
                parse_mode="Markdown"
            )
            await self._send_long(update, result)
            return

        fc_status = "✅ Firecrawl aktif" if self.rnd_module.has_firecrawl() else "⚠️ Firecrawl belum dikonfigurasi"

        keyboard = [
            [InlineKeyboardButton("🔍 Riset Calon Mitra", callback_data="rnd_riset")],
            [InlineKeyboardButton("📈 Analisis SWOT", callback_data="rnd_swot")],
            [InlineKeyboardButton("📋 Buat Proposal Kemitraan", callback_data="rnd_proposal")],
            [InlineKeyboardButton("🔬 Riset Teknologi", callback_data="rnd_tech")],
            [InlineKeyboardButton("🕷️ Scrape Website", callback_data="rnd_scrape")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"🔬 *Modul R&D*\n_{fc_status}_\n\nPilih fungsi atau langsung ketik:\n`/rnd Yayasan Darul Hikam`",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

    async def sosmed(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not await check_user_allowed(user_id):
            return

        keyboard = [
            [InlineKeyboardButton("✍️ Buat Konten", callback_data="sosmed_konten")],
            [InlineKeyboardButton("📊 Analisis Performa", callback_data="sosmed_analisis")],
            [InlineKeyboardButton("📅 Content Calendar", callback_data="sosmed_kalender")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Modul Social Media:", reply_markup=reply_markup)

    async def resources(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not await check_user_allowed(user_id):
            return

        keyboard = [
            [InlineKeyboardButton("📤 Upload Dokumen", callback_data="res_upload")],
            [InlineKeyboardButton("🔍 Semantic Search", callback_data="res_search")],
            [InlineKeyboardButton("🏢 Kelola Produk", callback_data="res_produk")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Modul Resources:", reply_markup=reply_markup)

    async def credit(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not await check_user_allowed(user_id):
            return
        if not update.message:
            return

        msg = await update.message.reply_text("⏳ Mengambil data kredit dari semua provider...")

        # ── Data lokal (DB) ───────────────────────────────────────────────
        async with aiosqlite.connect(self.db_path) as db:
            summary  = await get_user_usage(db, user_id)
            by_model = await get_usage_by_model(db, user_id)
            provider, model_name = await get_user_model(db, user_id)

        # ── Cek saldo real dari API ───────────────────────────────────────
        import asyncio as _aio
        or_data, ant_data = await _aio.gather(
            check_openrouter_balance(),
            check_anthropic_balance(),
        )

        now_str = _dt.now().strftime("%d/%m/%Y %H:%M")
        total_tokens = summary["total_input"] + summary["total_output"]

        lines = [
            "💳 *LAPORAN KREDIT API*",
            f"_Diperbarui: {now_str}_",
            "",
        ]

        # ── OpenRouter ────────────────────────────────────────────────────
        lines.append("🌐 *OpenRouter*")
        if "error" in or_data:
            lines.append(f"  ❌ {or_data['error']}")
        else:
            usage_usd  = or_data.get("usage", 0) or 0
            limit_usd  = or_data.get("limit")
            remaining  = or_data.get("remaining")
            is_free    = or_data.get("is_free_tier", False)
            label      = or_data.get("label", "")

            lines.append(f"  📛 Key: `{label or 'default'}`")
            lines.append(f"  💸 Terpakai: *${usage_usd:.4f}* (~Rp {usage_usd*IDR_RATE:,.0f})")
            if limit_usd is not None:
                lines.append(f"  🏦 Limit: *${limit_usd:.2f}*")
                if remaining is not None:
                    pct = (remaining / limit_usd * 100) if limit_usd > 0 else 0
                    bar = "█" * int(pct / 10) + "░" * (10 - int(pct / 10))
                    lines.append(f"  ✅ Sisa: *${remaining:.4f}* [{bar}] {pct:.0f}%")
            else:
                lines.append("  ♾️ Limit: tidak terbatas / pay-as-you-go")
            if is_free:
                lines.append("  🆓 Tier: Free")
        lines.append("")

        # ── Anthropic ─────────────────────────────────────────────────────
        lines.append("🤖 *Anthropic Claude*")
        if "error" in ant_data:
            lines.append(f"  ❌ {ant_data['error']}")
        else:
            status = ant_data.get("key_status", "?")
            icon = "✅" if status == "aktif" else "❌"
            lines.append(f"  {icon} API Key: *{status}*")
            lines.append(f"  🔗 Saldo: [console.anthropic.com](https://console.anthropic.com/settings/billing)")
        lines.append("")

        # ── Penggunaan lokal (DB) ─────────────────────────────────────────
        lines.append("📊 *Penggunaan Lokal Bot*")
        lines.append(f"  🔢 Total request: *{summary['total_calls']}x*")
        lines.append(f"  📥 Token input  : *{summary['total_input']:,}*")
        lines.append(f"  📤 Token output : *{summary['total_output']:,}*")
        lines.append(f"  📈 Total token  : *{total_tokens:,}*")
        lines.append(f"  💰 Est. biaya   : *${summary['total_cost']:.6f}* (~Rp {summary['total_cost']*IDR_RATE:,.0f})")
        lines.append("")

        if by_model:
            lines.append("📋 *Per Model:*")
            for row in by_model:
                prov, mdl, inp, out, cost, calls = row
                mdl_short = mdl.split("/")[-1] if "/" in mdl else mdl
                lines.append(f"  • `{mdl_short}` ({prov}) — {calls}x · ${cost:.4f}")
            lines.append("")

        model_short = model_name.split("/")[-1] if "/" in model_name else model_name
        lines += [
            f"⚙️ *Model aktif:* `{model_short}` via *{provider}*",
        ]

        text = "\n".join(lines)
        await msg.edit_text(text, parse_mode="Markdown", disable_web_page_preview=True)

        # ── Simpan ke memory ──────────────────────────────────────────────
        self._save_credit_memory(or_data, ant_data, summary, provider, model_name, now_str)

    def _save_credit_memory(self, or_data: dict, ant_data: dict,
                            summary: dict, provider: str, model_name: str,
                            now_str: str):
        """Simpan snapshot kredit terakhir ke file memory."""
        from pathlib import Path
        mem_dir = Path(__file__).parent.parent.parent.parent / \
                  ".claude" / "projects" / "e--ArunikaAgenticAi-Ver2" / "memory"
        mem_dir.mkdir(parents=True, exist_ok=True)
        mem_file = mem_dir / "credit_snapshot.md"

        or_usage     = or_data.get("usage",     0) or 0
        or_limit     = or_data.get("limit")
        or_remaining = or_data.get("remaining")
        ant_status   = ant_data.get("key_status", "?")
        total_tokens = summary["total_input"] + summary["total_output"]

        content = f"""---
name: credit-snapshot
description: Snapshot kredit API terakhir dicek oleh user via /credit
metadata:
  type: project
---

**Dicek pada:** {now_str}

## OpenRouter
- Terpakai : ${or_usage:.4f}
- Limit     : {"$" + f"{or_limit:.2f}" if or_limit else "unlimited"}
- Sisa      : {"$" + f"{or_remaining:.4f}" if or_remaining is not None else "N/A"}
- Free tier : {or_data.get("is_free_tier", False)}

## Anthropic
- API Key   : {ant_status}
- Saldo     : cek manual di console.anthropic.com/settings/billing

## Penggunaan Bot (lokal DB)
- Total request : {summary["total_calls"]}x
- Total token   : {total_tokens:,}
- Est. biaya    : ${summary["total_cost"]:.6f}

## Model Aktif
- Provider : {provider}
- Model    : {model_name}

**Why:** Disimpan otomatis setiap /credit agar konteks kredit tersedia di sesi berikutnya.
**How to apply:** Gunakan sebagai referensi saat user bertanya sisa kredit atau budget AI.
"""
        mem_file.write_text(content, encoding="utf-8")

        # Update MEMORY.md index
        memory_index = mem_dir / "MEMORY.md"
        entry = f"- [Credit Snapshot](credit_snapshot.md) — Saldo API terakhir dicek: {now_str}\n"
        if memory_index.exists():
            existing = memory_index.read_text(encoding="utf-8")
            if "credit_snapshot.md" in existing:
                import re
                existing = re.sub(r"- \[Credit Snapshot\].*\n", entry, existing)
                memory_index.write_text(existing, encoding="utf-8")
            else:
                memory_index.write_text(existing.rstrip() + "\n" + entry, encoding="utf-8")
        else:
            memory_index.write_text(entry, encoding="utf-8")

    async def fungsi(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not await check_user_allowed(user_id):
            return

        async with aiosqlite.connect(self.db_path) as db:
            provider, model_name = await get_user_model(db, user_id)

        model_short = model_name.split("/")[-1] if "/" in model_name else model_name

        part1 = (
            "📋 *DAFTAR FUNGSI REFLECTIVE KOALA*\n"
            f"_Model: {model_short} ({provider})_\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🧠 *LETTA MEMORY — Infinite Context*\n"
            "  Memori jangka panjang tanpa batas (diadaptasi dari Letta/MemGPT)\n"
            "  ├ Core Memory: fakta tentang user & bot (selalu aktif)\n"
            "  ├ Archival Memory: penyimpanan tak terbatas dengan full-text search\n"
            "  ├ Auto-update: Claude mengedit memori sendiri saat diperlukan\n"
            "  └ /memori — lihat, cari & kelola semua memori\n\n"
            "⏰ *AGEN 24/7 — Tugas Otonom*\n"
            "  /agen24 <tugas> | <jadwal> — jadwalkan tugas berjalan otomatis\n"
            "  Format jadwal: 'setiap hari 08:00' | 'setiap senin 09:00' | 'setiap 2 jam'\n"
            "  /agen24 list — lihat daftar tugas terjadwal\n\n"

            "🤖 *AI & MODEL*\n"
            "  /settings — Pilih provider: Anthropic / OpenRouter / LM Studio\n"
            "    ├ Anthropic: Haiku 4.5, Sonnet 4.6, Opus 4.7\n"
            "    ├ OpenRouter: Claude, Gemini, GPT, Kimi, Qwen, dll\n"
            "    └ LM Studio: model lokal di komputer\n"
            "  /model — Shortcut pilih model\n"
            "  /compress — Padatkan riwayat percakapan (hemat token)\n"
            "  /credit — Cek saldo & biaya API real-time\n\n"

            "📄 *DOKUMEN & PDF*\n"
            "  /pdf <judul> — Generate PDF dari teks/markdown APAPUN\n"
            "    ├ Laporan riset, notulensi, artikel, strategi\n"
            "    └ Kirim judul → kirim isi → PDF dikirim sebagai file\n"
            "  /sek → Buat Surat — Surat resmi ATG (letterhead + logo PDF)\n"
            "    ├ AI Draft Otomatis — deskripsikan → AI buat surat\n"
            "    ├ Tulis Manual — isi form step-by-step\n"
            "    ├ Download PDF langsung\n"
            "    └ Kirim via Email SMTP\n"
            "  Kirim file PDF/DOCX/TXT → AI baca & analisis isinya\n\n"

            "📸 *GAMBAR, FOTO & SCREENSHOT*\n"
            "  Kirim foto/screenshot sebagai FOTO → AI Vision analisis\n"
            "  Kirim PNG/JPG/WebP sebagai FILE → AI Vision analisis\n"
            "  /gambar <deskripsi> — Generate gambar AI\n"
            "    ├ FLUX 1.1 Pro (kualitas terbaik)\n"
            "    ├ FLUX Schnell (cepat & murah)\n"
            "    └ DALL-E 3 (kreatif)\n\n"
        )

        part2 = (
            "🔮 *HERMES AGENT* (via /h <tugas> atau /hermes <tugas>)\n"
            "  Agen otonom dengan tool calling native — paling canggih\n"
            "  Tools yang tersedia:\n"
            "    ├ 🌐 web_search — Cari info real-time di internet\n"
            "    ├ 📂 read_file — Baca file dari proyek bot\n"
            "    ├ 💾 write_file — Tulis/simpan file baru\n"
            "    ├ 🧠 remember — Simpan ke memori permanen antar sesi\n"
            "    ├ 🐍 run_python — Eksekusi kode Python\n"
            "    └ ⚡ create_skill — Buat skill baru secara mandiri\n"
            "  Contoh: /h Riset AI tools 2025 & simpan ke laporan PDF\n\n"

            "🤖 *AGEN OTONOM* (via /agen <tugas>)\n"
            "  Plan → Research (web) → Synthesize → Deliver\n"
            "  Contoh: /agen Bandingkan GPT-4o vs Gemini 2.5 Pro\n\n"

            "🔍 *RISET & DEVELOPMENT* (via /rnd)\n"
            "    ├ Riset calon mitra bisnis (web search + AI)\n"
            "    ├ Analisis SWOT komprehensif\n"
            "    ├ Buat proposal kemitraan\n"
            "    ├ Riset teknologi terkini\n"
            "    └ Scrape & ringkas website\n\n"

            "💼 *KARIR* (via /karir)\n"
            "    ├ Evaluasi lowongan kerja (A-F scoring — 7 blok analisis)\n"
            "    ├ Buat CV profesional ATS-optimized\n"
            "    ├ Riset perusahaan untuk persiapan interview\n"
            "    └ Analisis evolusi bot (Hermes methodology)\n\n"

            "📝 *SEKRETARIS* (via /sek)\n"
            "    ├ Surat resmi PDF\n"
            "    ├ Presentasi\n"
            "    ├ Notulensi meeting\n"
            "    ├ Set agenda\n"
            "    └ Set reminder\n\n"

            "📱 *SOCIAL MEDIA* (via /sosmed)\n"
            "    ├ Konten IG/FB/TikTok/YouTube\n"
            "    ├ Analisis performa konten\n"
            "    └ Content calendar\n\n"
        )

        part3 = (
            "📧 *KOMUNIKASI*\n"
            "  /email — Kirim email resmi via SMTP ATG\n"
            "    ├ Tulis Manual\n"
            "    ├ AI Draft email\n"
            "    └ Test koneksi SMTP\n\n"

            "🗂 *KNOWLEDGE BASE* (via /resources)\n"
            "    ├ Upload dokumen\n"
            "    ├ Semantic search (RAG)\n"
            "    └ Kelola produk & program ATG\n\n"

            "⚙️ *AUTOMATION* (via /auto)\n"
            "    ├ Jalankan Python script\n"
            "    ├ Set cron job\n"
            "    └ Web scraping\n\n"

            "🛠 *DEVELOPER & PENGEMBANGAN*\n"
            "  /code — Python REPL (jalankan kode langsung)\n"
            "  /perbaiki <deskripsi> — Bot improve dirinya sendiri\n"
            "  /recall <kata> — Cari percakapan lama\n"
            "  /tools — Lihat semua skill & tools (ringkasan)\n\n"

            "📊 *PENGATURAN & MONITORING*\n"
            "  /settings — Provider & model AI\n"
            "  /credit — Saldo & biaya API\n"
            "  /compress — Padatkan konteks\n"
            "  /fungsi — Daftar ini\n"
            "  /start — Menu utama\n"
            "  /help — Panduan\n\n"

            "💬 *CHAT BEBAS*\n"
            "  Ketik pertanyaan apapun → dijawab AI\n"
            "  Konteks tersimpan otomatis\n"
            "  Kirim foto → Vision AI analisis\n"
            "  Kirim file → AI baca & analisis\n"
        )

        for part in (part1, part2, part3):
            await update.message.reply_text(part, parse_mode="Markdown")

    async def compress(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not await check_user_allowed(user_id):
            return

        msg = await update.message.reply_text(
            "⏳ Memadatkan percakapan...\nProses ini mungkin membutuhkan beberapa detik."
        )

        result = await self.agent.compress_context(user_id)

        if "error" in result:
            if result["error"] == "too_short":
                await msg.edit_text(
                    f"ℹ️ Percakapan terlalu pendek untuk dipadatkan.\n"
                    f"Saat ini hanya ada *{result['count']} pesan*.\n"
                    f"Minimal 6 pesan sebelum bisa dikompresi.",
                    parse_mode="Markdown"
                )
            else:
                await msg.edit_text(f"❌ Gagal memadatkan: {result['error']}")
            return

        saved_pct = 0
        if result["before_tokens_est"] > 0:
            saved_pct = int(result["saved_tokens_est"] / result["before_tokens_est"] * 100)

        report = (
            f"✅ *Percakapan berhasil dipadatkan!*\n\n"
            f"📊 *Statistik Kompresi:*\n"
            f"  • Pesan sebelum: *{result['before_count']}*\n"
            f"  • Pesan sesudah: *{result['after_count']}* (ringkasan)\n"
            f"  • Estimasi token sebelum: *~{result['before_tokens_est']:,}*\n"
            f"  • Estimasi token sesudah: *~{result['after_tokens_est']:,}*\n"
            f"  • Token dihemat: *~{result['saved_tokens_est']:,}* ({saved_pct}%)\n\n"
            f"📝 *Ringkasan percakapan:*\n"
            f"_{result['summary'][:400]}{'...' if len(result['summary']) > 400 else ''}_\n\n"
            f"💡 Percakapan selanjutnya akan menggunakan ringkasan ini sebagai konteks."
        )

        await msg.edit_text(report, parse_mode="Markdown")

    async def model_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not await check_user_allowed(user_id):
            return

        # Samakan alur dengan /settings:
        # tampilkan provider (Anthropic / OpenRouter / LM Studio) dulu,
        # lalu provider_callback akan menampilkan daftar modelnya.
        await self.settings(update, context)
        return

        try:
            models = await fetch_anthropic_models(settings.anthropic_api_key, settings.anthropic_base_url)
        except Exception as e:
            await msg.edit_text(f"❌ Gagal fetch model: {e}")
            return

        if not models:
            await msg.edit_text("❌ Tidak ada model yang tersedia untuk API key ini.")
            return

        keyboard = []
        for model_id, display_name in models:
            label = f"✅ {display_name}" if model_id == current_model else display_name
            keyboard.append([InlineKeyboardButton(label, callback_data=f"setmodel_{model_id}")])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await msg.edit_text(
            f"🤖 *Pilih Model Claude*\n\nModel aktif: `{current_model}`\n\nDaftar model tersedia di API key Anda:",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

    async def setmodel_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        user_id = query.from_user.id
        model_id = query.data.split("_", 1)[1]
        provider = context.user_data.get("selected_provider", "anthropic")

        async with aiosqlite.connect(self.db_path) as db:
            await set_user_model(db, user_id, provider, model_id)

        await self.agent.init_model(provider, model_id)

        display = (
            (ANTHROPIC_MODELS.get(model_id) if provider == "anthropic" else None)
            or (OPENROUTER_MODELS.get(model_id) if provider == "openrouter" else None)
            or f"🖥️ {model_id} (Lokal)" if provider == "lmstudio"
            else f"🖥️ {model_id}"
        )

        await query.edit_message_text(
            f"✅ *Model berhasil diganti!*\n\n"
            f"🤖 Model aktif: `{display}`\n"
            f"🔌 Provider: *{provider}*\n\n"
            f"Sekarang Anda bisa langsung chat menggunakan model baru.",
            parse_mode="Markdown"
        )

    async def automation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not await check_user_allowed(user_id):
            return

        keyboard = [
            [InlineKeyboardButton("▶️ Jalankan Script", callback_data="auto_run")],
            [InlineKeyboardButton("⏰ Set Cron Job", callback_data="auto_cron")],
            [InlineKeyboardButton("🕷️ Web Scraping", callback_data="auto_scrape")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Modul Automation:", reply_markup=reply_markup)

    # ──────────────────────────────────────────────────────────────────────
    # PDF GENERATOR  (/pdf) — generate PDF dari teks/markdown apapun
    # ──────────────────────────────────────────────────────────────────────

    async def pdf_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not await check_user_allowed(user_id):
            return
        if not update.message:
            return

        title_arg = " ".join(context.args).strip() if context.args else ""

        if not title_arg:
            await update.message.reply_text(
                "📄 *Generator PDF*\n\n"
                "Generate PDF dari TEKS APAPUN — laporan, riset, artikel, notulensi.\n\n"
                "**Cara 1:** `/pdf <judul>` lalu kirim isi konten\n"
                "**Cara 2:** `/pdf` → bot minta judul dulu\n\n"
                "✅ *Contoh:*\n"
                "• `/pdf Laporan Riset AI Tools 2025`\n"
                "• `/pdf Notulensi Rapat Direksi 29 Mei`\n"
                "• `/pdf Strategi Marketing Q2 2025`\n\n"
                "_Untuk surat resmi dengan letterhead ATG → gunakan /sek_",
                parse_mode="Markdown",
            )
            if context.user_data is not None:
                context.user_data["pdf_state"] = "waiting_title"
            return

        # Ada judul dari args — minta konten
        if context.user_data is not None:
            context.user_data["pdf_state"] = "waiting_content"
            context.user_data["pdf_title"] = title_arg

        await update.message.reply_text(
            f"📄 *Judul PDF:* `{title_arg}`\n\n"
            "Sekarang kirim **isi konten** dokumen.\n"
            "Boleh panjang, boleh pakai format Markdown:\n"
            "• `## Heading` untuk judul bagian\n"
            "• `**teks tebal**` untuk bold\n"
            "• `- item` untuk bullet list\n\n"
            "_Bot akan generate PDF dan kirim sebagai file._",
            parse_mode="Markdown",
        )

    async def _handle_pdf_state(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        pdf_state: str,
        user_message: str,
    ):
        msg = update.message
        if not msg or context.user_data is None:
            return
        ud = context.user_data

        if pdf_state == "waiting_title":
            ud["pdf_title"] = user_message.strip()
            ud["pdf_state"] = "waiting_content"
            await msg.reply_text(
                f"📄 *Judul:* `{user_message.strip()}`\n\n"
                "Kirim isi konten dokumen (boleh panjang, boleh pakai Markdown):",
                parse_mode="Markdown",
            )
            return

        if pdf_state == "waiting_content":
            ud.pop("pdf_state", None)
            title = ud.pop("pdf_title", "Dokumen ATG")
            content = user_message.strip()

            if not content:
                await msg.reply_text("❌ Konten tidak boleh kosong.")
                return

            # Jika user kirim brief pendek (bukan konten lengkap),
            # generate konten dengan AI yang merujuk hasil riset sebelumnya.
            user_id = update.effective_user.id if update.effective_user else 0
            if len(content) < 400:
                status = await msg.reply_text(
                    f"⏳ Membuat PDF: *{title}*\n"
                    f"{self._render_progress_bar(1, 4, 'Membaca riset sebelumnya')}",
                    parse_mode="Markdown",
                )
                try:
                    riset_context = await self._get_research_context(
                        user_id, f"{title} {content}"
                    )
                    if riset_context:
                        await status.edit_text(
                            f"⏳ Membuat PDF: *{title}*\n"
                            f"{self._render_progress_bar(2, 4, 'Menyusun konten dengan AI')}",
                            parse_mode="Markdown",
                        )
                        router = await self._ensure_model_router(user_id)
                        ai_prompt = f"""Buatkan dokumen profesional berformat Markdown.

JUDUL: {title}
BRIEF DARI USER: {content}

RISET / KONTEKS SEBELUMNYA (WAJIB dijadikan sumber utama — sebut data konkret,
angka, profil, fakta nyata yang relevan):
{riset_context}

INSTRUKSI:
1. Tulis dokumen substansial (minimum 800 kata) yang merujuk DATA NYATA dari riset.
2. Struktur: ringkasan eksekutif → latar belakang → analisis → kesimpulan → rekomendasi.
3. Pakai *bold* tunggal (bukan **double**), bullet •, dan section heading.
4. JANGAN pakai placeholder generik — semua isi harus konkret dari riset/brief.

Tulis langsung dokumennya tanpa prefix penjelasan."""
                        try:
                            generated, _ = await router.call(
                                messages=[{"role": "user", "content": ai_prompt}],
                                temperature=0.4,
                                max_tokens=4000,
                            )
                            if generated and len(generated) > 400:
                                content = generated
                        except Exception as _e:
                            logger.warning("Gagal generate konten PDF dari AI: %s", _e)
                    await status.edit_text(
                        f"⏳ Membuat PDF: *{title}*\n"
                        f"{self._render_progress_bar(3, 4, 'Menulis PDF')}",
                        parse_mode="Markdown",
                    )
                except Exception as _e:
                    logger.warning("Gagal enrich konten PDF: %s", _e)
            else:
                status = await msg.reply_text(
                    f"⏳ Membuat PDF: *{title}*...", parse_mode="Markdown"
                )

            try:
                pdf_path = await generate_document_pdf_async(title, content)
                await status.edit_text(f"📄 *{title}* — PDF selesai ✅", parse_mode="Markdown")
                with open(pdf_path, "rb") as f:
                    safe_name = "".join(
                        c if c.isalnum() or c in " -_" else "" for c in title[:40]
                    ).strip().replace(" ", "_") or "dokumen"
                    await msg.reply_document(
                        document=f,
                        filename=f"{safe_name}.pdf",
                        caption=(
                            f"📄 *{title}*\n"
                            f"✅ PDF berhasil dibuat oleh Reflective Koala ATG"
                        ),
                        parse_mode="Markdown",
                    )
            except Exception as e:
                logger.exception("PDF generation error: %s", e)
                await status.edit_text(f"❌ Gagal membuat PDF: {e}")

    # ──────────────────────────────────────────────────────────────────────
    # TOOLS MENU  (/tools) — tampilkan semua skill & tools
    # ──────────────────────────────────────────────────────────────────────

    async def tools_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not await check_user_allowed(user_id):
            return
        if not update.message:
            return

        text = (
            "🛠️ *SEMUA SKILL & TOOLS — REFLECTIVE KOALA ATG*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

            "📄 *DOKUMEN & PDF*\n"
            "  /pdf <judul> — Generate PDF dari teks/markdown apapun\n"
            "  /sek → Buat Surat — Surat resmi ATG (letterhead + logo)\n"
            "  Kirim file PDF/DOCX/TXT → bot membaca & menganalisis\n\n"

            "📸 *GAMBAR & SCREENSHOT*\n"
            "  Kirim foto/screenshot → AI Vision menganalisis\n"
            "  Kirim gambar sebagai file → AI Vision menganalisis\n"
            "  /gambar <deskripsi> — Generate gambar AI (DALL-E, FLUX)\n\n"

            "🔮 *HERMES AGENT TOOLS* (via /h <tugas>)\n"
            "  🌐 web_search — Cari informasi real-time di internet\n"
            "  📂 read_file — Baca file dari proyek bot\n"
            "  💾 write_file — Tulis/simpan file baru\n"
            "  🧠 remember — Simpan ke memori permanen antar sesi\n"
            "  🐍 run_python — Eksekusi kode Python\n"
            "  ⚡ create_skill — Buat skill baru secara mandiri\n\n"

            "🤖 *AGEN OTONOM* (via /agen <tugas>)\n"
            "  Plan → Research (web) → Synthesize → Deliver\n\n"

            "💼 *KARIR* (via /karir)\n"
            "  Evaluasi lowongan (A-F scoring)\n"
            "  Buat CV profesional ATS-optimized\n"
            "  Riset perusahaan untuk interview\n"
            "  Analisis evolusi bot\n\n"

            "🔬 *R&D* (via /rnd)\n"
            "  Riset calon mitra bisnis (web search)\n"
            "  Analisis SWOT komprehensif\n"
            "  Buat proposal kemitraan\n"
            "  Riset teknologi terkini\n"
            "  Scrape & ringkas website\n\n"

            "📝 *SEKRETARIS* (via /sek)\n"
            "  Buat surat resmi PDF (letterhead ATG)\n"
            "  Presentasi, notulensi, agenda, reminder\n\n"

            "💬 *KOMUNIKASI*\n"
            "  /email — Kirim email via SMTP ATG\n"
            "  /recall — Cari percakapan lama\n\n"

            "⚙️ *UTILITAS*\n"
            "  /code — Jalankan Python script\n"
            "  /perbaiki — Improve bot dari deskripsi\n"
            "  /credit — Cek penggunaan & biaya API\n"
            "  /settings — Ganti model AI\n"
            "  /compress — Padatkan konteks percakapan\n"
        )

        await update.message.reply_text(text, parse_mode="Markdown")

    # ──────────────────────────────────────────────────────────────────────
    # HERMES AGENT  (/h) — NousResearch/hermes-agent tool-calling loop
    # ──────────────────────────────────────────────────────────────────────

    async def hermes_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not await check_user_allowed(user_id):
            return
        if not update.message:
            return

        task = " ".join(context.args).strip() if context.args else ""
        if not task:
            await update.message.reply_text(
                "🔮 *Hermes Agent* — Agen otonom dengan tool calling\n\n"
                "Hermes dapat menggunakan tools secara mandiri:\n"
                "🌐 web_search · 📂 read_file · 💾 write_file\n"
                "🧠 remember · 🐍 run_python · ⚡ create_skill\n\n"
                "✅ *Contoh:*\n"
                "• `/h Riset dan simpan ke file: tren AI Indonesia 2025`\n"
                "• `/h Baca src/config.py dan jelaskan strukturnya`\n"
                "• `/h Buat skill baru untuk membuat ringkasan meeting`\n"
                "• `/h Cari harga GPU terbaru lalu hitung estimasi budget training`\n\n"
                "Berbeda dengan /agen — Hermes menggunakan *tool calling native* "
                "dan bisa membuat skill baru secara mandiri.",
                parse_mode="Markdown",
            )
            return

        router = await self._ensure_model_router(user_id)

        import html as _html
        task_esc = _html.escape(task[:100])
        msg = await update.message.reply_text(
            f"🔮 <b>HERMES AGENT</b>\n\n"
            f"💼 <i>{task_esc}</i>\n\n"
            f"⚡ Memulai...",
            parse_mode="HTML",
        )

        async def on_progress(t: str):
            try:
                await msg.edit_text(t, parse_mode="HTML")
            except Exception as _pe:
                logger.debug("Progress edit failed: %s", _pe)
                try:
                    # Fallback: kirim tanpa formatting
                    import re as _re
                    plain = _re.sub(r"<[^>]+>", "", t)
                    await msg.edit_text(plain)
                except Exception:
                    pass

        generated_files: list = []
        async def on_file(file_path: str):
            generated_files.append(file_path)

        try:
            mem = self.agent.get_memory(user_id)
            result = await self.hermes.run(
                task, router,
                on_progress=on_progress,
                on_file=on_file,
                user_id=user_id,
                memory=mem,
            )
            try:
                await msg.edit_text(
                    f"🔮 <b>HERMES AGENT</b>\n\n"
                    f"💼 <i>{task_esc}</i>\n\n"
                    f"✅ Selesai — hasil di bawah ini.",
                    parse_mode="HTML",
                )
            except Exception:
                pass
            await self._send_long(update, result)
            # Kirim file PDF yang dihasilkan tool generate_pdf
            for fp in generated_files:
                try:
                    from pathlib import Path as _Path
                    with open(fp, "rb") as f:
                        stem = _Path(fp).stem
                        # Ambil bagian judul dari nama file (abaikan timestamp prefix)
                        parts = stem.split("_", 2)
                        label = parts[2].replace("_", " ") if len(parts) >= 3 else stem
                        await update.message.reply_document(
                            document=f,
                            filename=_Path(fp).name,
                            caption=f"📄 *{label}*\n_Dibuat oleh Hermes Agent ATG_",
                            parse_mode="Markdown",
                        )
                except Exception as ef:
                    logger.error("Gagal kirim file Hermes: %s", ef)
        except Exception as e:
            logger.exception("Hermes error: %s", e)
            await msg.edit_text(
                f"❌ Hermes gagal:\n`{e}`\n\n"
                f"💡 Tip: model yang dipilih mungkin tidak mendukung tool calling. "
                f"Coba ganti ke Claude atau GPT-4o via /settings.",
                parse_mode="Markdown",
            )

    async def recall_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not await check_user_allowed(user_id):
            return
        if not update.message:
            return

        query = " ".join(context.args).strip() if context.args else ""
        if not query:
            await update.message.reply_text(
                "🔍 *Recall Memory*\n\nCari percakapan lama:\n`/recall <kata kunci>`\n\n"
                "_Contoh: /recall surat penawaran_",
                parse_mode="Markdown",
            )
            return

        result = await self.hermes.recall(query, self.db_path, user_id)
        await update.message.reply_text(result, parse_mode="Markdown")

    # ──────────────────────────────────────────────────────────────────────
    # LETTA MEMORY  (/memori) — tampilkan & kelola infinite context memory
    # ──────────────────────────────────────────────────────────────────────

    async def memori_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not await check_user_allowed(user_id):
            return
        if not update.message:
            return

        mem = self.agent.get_memory(user_id)
        stats = await mem.get_stats()

        args = context.args or []
        sub  = args[0].lower() if args else ""

        if sub == "arsip":
            # Tampilkan archival memory
            entries = await mem.get_archival_entries(limit=15)
            if not entries:
                await update.message.reply_text(
                    "📚 *Archival Memory* — Kosong\n\n"
                    "Anda belum memiliki memori jangka panjang.\n"
                    "Saat chat dengan Claude, bot akan otomatis menyimpan info penting.",
                    parse_mode="Markdown",
                )
                return
            import json as _json
            lines = [f"📚 *Archival Memory* ({len(entries)} entri terbaru):\n"]
            for content, tags_json, created_at in entries:
                try:
                    tags = _json.loads(tags_json or "[]")
                except Exception:
                    tags = []
                tag_str  = " ".join(f"`{t}`" for t in tags) if tags else ""
                date_str = str(created_at)[:10]
                lines.append(f"• {date_str} {tag_str}\n  _{content[:120]}_\n")
            await self._send_long(update, "\n".join(lines))
            return

        if sub == "hapus":
            target = args[1].lower() if len(args) > 1 else "semua"
            if target in ("arsip", "archival"):
                await mem.clear_archival()
                await update.message.reply_text("✅ Archival memory dihapus.")
            elif target in ("persona",):
                await mem.clear_core("persona")
                await update.message.reply_text("✅ Core memory 'persona' direset.")
            elif target in ("human",):
                await mem.clear_core("human")
                await update.message.reply_text("✅ Core memory 'human' direset.")
            else:
                await mem.clear_core()
                await mem.clear_archival()
                await update.message.reply_text("✅ Semua memory direset ke default.")
            return

        # Default: tampilkan summary
        persona_preview = stats["persona"][:300] + "..." if len(stats["persona"]) > 300 else stats["persona"]
        human_preview   = stats["human"][:300]   + "..." if len(stats["human"]) > 300   else stats["human"]

        text = (
            "🧠 *LETTA MEMORY — Infinite Context*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📊 *Statistik:*\n"
            f"  • Core Memory Persona: {stats['persona_chars']:,} / 5,000 karakter\n"
            f"  • Core Memory Human:   {stats['human_chars']:,} / 5,000 karakter\n"
            f"  • Archival Memory:     {stats['archival_count']:,} entri\n\n"
            f"👤 *Persona (tentang bot):*\n_{persona_preview}_\n\n"
            f"🙋 *Human (tentang Anda):*\n_{human_preview}_\n\n"
            "📋 *Sub-perintah:*\n"
            "  `/memori arsip` — lihat archival memory\n"
            "  `/memori hapus arsip` — hapus archival memory\n"
            "  `/memori hapus semua` — reset semua memory\n\n"
            "💡 Memory diperbarui otomatis saat chat dengan model Claude."
        )
        await update.message.reply_text(text, parse_mode="Markdown")

    # ──────────────────────────────────────────────────────────────────────
    # 24/7 AGENT  (/agen24) — jadwalkan tugas otonom
    # ──────────────────────────────────────────────────────────────────────

    async def agen24_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not await check_user_allowed(user_id):
            return
        if not update.message:
            return

        args_str = " ".join(context.args).strip() if context.args else ""
        chat_id  = update.effective_chat.id if update.effective_chat else user_id

        if not args_str:
            await update.message.reply_text(
                "⏰ *Agen 24/7 — Tugas Otonom*\n\n"
                "Jadwalkan tugas yang berjalan otomatis tanpa interaksi.\n"
                "Hasil dikirim ke chat ini.\n\n"
                "📋 *Format:*\n"
                "`/agen24 <tugas> | <jadwal>`\n\n"
                "🕐 *Format jadwal:*\n"
                "• `setiap hari 08:00`\n"
                "• `setiap senin 09:00`\n"
                "• `setiap 2 jam`\n"
                "• `sekali 2026-06-15 10:00`\n\n"
                "✅ *Contoh:*\n"
                "`/agen24 Riset berita AI terbaru dan buat ringkasan | setiap hari 07:30`\n"
                "`/agen24 Cek harga dolar dan kirim laporan | setiap hari 08:00`\n\n"
                "📋 *Kelola:*\n"
                "`/agen24 list` — lihat semua tugas\n"
                "`/agen24 batal <id>` — batalkan tugas",
                parse_mode="Markdown",
            )
            return

        # List tasks
        if args_str.lower() in ("list", "daftar", "lihat"):
            tasks = await list_tasks(self.db_path, user_id)
            if not tasks:
                await update.message.reply_text(
                    "⏰ *Agen 24/7* — Belum ada tugas terjadwal.\n\n"
                    "Buat tugas baru: `/agen24 <tugas> | <jadwal>`",
                    parse_mode="Markdown",
                )
                return
            lines = ["⏰ *Tugas Agen 24/7 Anda:*\n"]
            for tid, task_desc, schedule, next_run, last_run, status in tasks:
                icon = "✅" if status == "active" else "⏹"
                nr_str = str(next_run)[:16] if next_run else "-"
                lr_str = str(last_run)[:16] if last_run else "belum pernah"
                lines.append(
                    f"{icon} `{tid}` — _{task_desc[:50]}_\n"
                    f"   Jadwal: {schedule}\n"
                    f"   Next: {nr_str} | Last: {lr_str}\n"
                )
            await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
            return

        # Cancel task
        if args_str.lower().startswith("batal "):
            tid = args_str.split(" ", 1)[1].strip()
            ok = await cancel_task(self.db_path, tid, user_id)
            if ok:
                await update.message.reply_text(f"✅ Tugas `{tid}` dibatalkan.", parse_mode="Markdown")
            else:
                await update.message.reply_text(f"❌ Tugas `{tid}` tidak ditemukan.", parse_mode="Markdown")
            return

        # Buat task baru — format: "deskripsi tugas | jadwal"
        if "|" not in args_str:
            await update.message.reply_text(
                "❌ Format salah. Gunakan:\n"
                "`/agen24 <tugas> | <jadwal>`\n\n"
                "_Contoh: /agen24 Riset AI terbaru | setiap hari 08:00_",
                parse_mode="Markdown",
            )
            return

        parts = args_str.split("|", 1)
        task_desc    = parts[0].strip()
        schedule_str = parts[1].strip()

        result = await create_task(self.db_path, user_id, chat_id, task_desc, schedule_str)

        if "error" in result:
            await update.message.reply_text(
                f"❌ *Gagal membuat tugas:*\n\n{result['error']}",
                parse_mode="Markdown",
            )
            return

        await update.message.reply_text(
            f"✅ *Tugas 24/7 berhasil dibuat!*\n\n"
            f"🆔 ID: `{result['id']}`\n"
            f"📋 Tugas: _{result['task']}_\n"
            f"🕐 Jadwal: {result['schedule']}\n"
            f"⏰ Eksekusi pertama: *{result['next_run']}*\n\n"
            f"Untuk membatalkan: `/agen24 batal {result['id']}`",
            parse_mode="Markdown",
        )

    # ──────────────────────────────────────────────────────────────────────
    # KARIR  (/karir) — Career-Ops methodology
    # ──────────────────────────────────────────────────────────────────────

    async def karir(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not await check_user_allowed(user_id):
            return
        if not update.message:
            return

        # Support inline args: /karir eval <url atau teks>
        args = " ".join(context.args).strip() if context.args else ""
        if args:
            router = await self._ensure_model_router(user_id)
            msg = await update.message.reply_text(
                f"💼 *Evaluasi Pekerjaan*\n\n"
                f"{self._render_progress_bar(1, 3, 'Analyzing job')}\n\n"
                "Menganalisis lowongan kerja...",
                parse_mode="Markdown",
            )
            step_counter = [1]
            async def _prog(t):
                step_counter[0] += 1
                try:
                    await msg.edit_text(
                        f"💼 *Evaluasi Pekerjaan*\n\n"
                        f"{self._render_progress_bar(min(step_counter[0], 3), 3, t)}\n\n"
                        f"{t}...",
                        parse_mode="Markdown"
                    )
                except Exception: pass
            result = await self.karir_module.eval_pekerjaan(args, router, on_progress=_prog)
            await msg.edit_text(
                f"💼 *Evaluasi Pekerjaan*\n\n"
                f"{self._render_progress_bar(3, 3, 'Complete ✅')}\n\n"
                "Hasil evaluasi siap:",
                parse_mode="Markdown"
            )
            await self._send_long(update, result)
            return

        fc_ok = "✅ Web search aktif" if self.karir_module.has_firecrawl() else "⚠️ Firecrawl belum dikonfigurasi"
        keyboard = [
            [InlineKeyboardButton("💼 Evaluasi Lowongan Kerja", callback_data="karir_eval")],
            [InlineKeyboardButton("📄 Buat CV Profesional", callback_data="karir_cv")],
            [InlineKeyboardButton("🏢 Riset Perusahaan", callback_data="karir_riset")],
            [InlineKeyboardButton("🧬 Evolusi Bot (Hermes)", callback_data="karir_evolusi")],
        ]
        await update.message.reply_text(
            f"💼 *Modul Karir*\n_{fc_ok}_\n\n"
            "Pilih fungsi atau langsung kirim:\n"
            "`/karir <URL atau deskripsi lowongan>`",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    async def karir_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        if not query or not query.data or context.user_data is None:
            return
        await query.answer()
        data = query.data

        if data == "karir_eval":
            context.user_data["karir_state"] = "eval"
            await query.edit_message_text(
                "💼 *Evaluasi Lowongan Kerja*\n\n"
                "Kirim salah satu:\n"
                "• URL lowongan (LinkedIn, Jobstreet, Glints, dll)\n"
                "• Teks deskripsi pekerjaan (paste langsung)\n\n"
                "_Contoh: https://linkedin.com/jobs/view/..._",
                parse_mode="Markdown",
            )

        elif data == "karir_cv":
            context.user_data["karir_state"] = "cv_info"
            await query.edit_message_text(
                "📄 *Buat CV Profesional*\n\n"
                "Ceritakan tentang dirimu (pengalaman, keahlian, pendidikan) "
                "dan posisi/perusahaan yang ditarget:\n\n"
                "_Contoh: Saya software engineer 5 tahun di fintech, "
                "ingin apply ke posisi AI Engineer di startup unicorn..._",
                parse_mode="Markdown",
            )

        elif data == "karir_riset":
            context.user_data["karir_state"] = "riset"
            await query.edit_message_text(
                "🏢 *Riset Perusahaan*\n\n"
                "Masukkan nama perusahaan yang ingin diriset:\n\n"
                "_Contoh: Gojek, Tokopedia, Telkom Indonesia, Google_",
                parse_mode="Markdown",
            )

        elif data == "karir_evolusi":
            context.user_data["karir_state"] = "evolusi"
            await query.edit_message_text(
                "🧬 *Evolusi Bot — Hermes Methodology*\n\n"
                "Tempel beberapa contoh percakapan atau keluhan tentang bot ini.\n"
                "AI akan menganalisis pola dan menyarankan perbaikan.\n\n"
                "_Atau ketik 'auto' untuk gunakan log percakapan terbaru_",
                parse_mode="Markdown",
            )

    async def _handle_karir_state(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        karir_state: str,
        user_message: str,
    ):
        msg = update.message
        if not msg or context.user_data is None:
            return
        context.user_data.pop("karir_state", None)
        user_id = update.effective_user.id if update.effective_user else 0
        router = await self._ensure_model_router(user_id)

        status = await msg.reply_text("⏳ AI sedang memproses...")

        async def on_progress(t: str):
            try: await status.edit_text(t, parse_mode="Markdown")
            except Exception: pass

        try:
            if karir_state == "eval":
                result = await self.karir_module.eval_pekerjaan(user_message, router, on_progress)

            elif karir_state == "cv_info":
                result = await self.karir_module.buat_cv(user_message, "", router, on_progress)

            elif karir_state == "riset":
                result = await self.karir_module.riset_perusahaan(user_message, router, on_progress)

            elif karir_state == "evolusi":
                if user_message.strip().lower() == "auto":
                    hist = await self.agent.context_manager.get_context(user_id, limit=30)
                    samples = "\n".join(
                        f"[{m['role'].upper()}]: {str(m['content'])[:300]}"
                        for m in hist
                    ) if hist else "Tidak ada riwayat percakapan tersimpan."
                else:
                    samples = user_message
                result = await self.karir_module.analisis_evolusi(samples, router, on_progress)

            else:
                result = "❌ State tidak dikenal."

            await status.edit_text(
                f"{self._render_progress_bar(3, 3, 'Complete ✅')}\n\n"
                "Hasil siap:",
                parse_mode="Markdown"
            )
            await self._send_long(update, result)

        except Exception as e:
            logger.exception("Karir handler error: %s", e)
            await status.edit_text(f"❌ Gagal: {e}")

    # ──────────────────────────────────────────────────────────────────────
    # AGEN OTONOM  (/agen) — CowAgent methodology
    # ──────────────────────────────────────────────────────────────────────

    async def agen_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not await check_user_allowed(user_id):
            return
        if not update.message:
            return

        task = " ".join(context.args).strip() if context.args else ""
        if not task:
            fc_ok = "✅ Web search aktif" if self.agen_module.has_firecrawl() else "⚠️ Firecrawl belum dikonfigurasi (hanya analisis AI)"
            await update.message.reply_text(
                "🤖 *Agen Otonom*\n"
                f"_{fc_ok}_\n\n"
                "Berikan tugas kompleks yang memerlukan riset dan analisis multi-langkah.\n\n"
                "✅ *Contoh:*\n"
                "• `/agen Riset AI tools terbaik 2025 untuk startup Indonesia`\n"
                "• `/agen Bandingkan GPT-4o vs Gemini 2.5 Pro untuk use case dokumen`\n"
                "• `/agen Buat strategi konten LinkedIn untuk perusahaan AI B2B`\n"
                "• `/agen Analisis tren adopsi AI di industri kesehatan Indonesia`",
                parse_mode="Markdown",
            )
            return

        router = await self._ensure_model_router(user_id)
        msg = await update.message.reply_text(
            f"🤖 *Agen Otonom*\n\n📋 Tugas: `{task[:100]}`\n\n⏳ Membuat rencana...",
            parse_mode="Markdown",
        )

        async def on_progress(t: str):
            try: await msg.edit_text(t, parse_mode="Markdown")
            except Exception: pass

        try:
            result = await self.agen_module.run(task, router, on_progress=on_progress)
            await msg.edit_text(
                f"🤖 *Agen Otonom*\n\n"
                f"{self._render_progress_bar(4, 4, 'Complete ✅')}\n\n"
                "Tugas selesai — hasil di bawah ini:",
                parse_mode="Markdown"
            )
            await self._send_long(update, result)
        except Exception as e:
            logger.exception("Agen error: %s", e)
            await msg.edit_text(f"❌ Agen gagal menyelesaikan tugas:\n{e}")

    async def gambar(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not await check_user_allowed(user_id):
            return

        prompt = " ".join(context.args).strip() if context.args else ""

        if not prompt:
            keyboard = [
                [InlineKeyboardButton(label, callback_data=f"img_{mid}")]
                for mid, label in OPENROUTER_IMAGE_MODELS.items()
            ]
            await update.message.reply_text(
                "🎨 *Generator Gambar AI*\n\n"
                "Pilih model lalu kirim deskripsi gambar:\n\n"
                "✅ *Contoh prompt:*\n"
                "• `logo perusahaan teknologi modern biru minimalis`\n"
                "• `poster seminar AI profesional 2025`\n"
                "• `konten instagram produk skincare elegan aesthetic`\n"
                "• `infografis langkah-langkah investasi saham`\n\n"
                "Atau langsung: `/gambar <deskripsi>`",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown",
            )
            return

        # Ambil model pilihan dari user_data, default FLUX Pro
        img_model = context.user_data.get("img_model", "black-forest-labs/flux-1.1-pro")
        model_label = OPENROUTER_IMAGE_MODELS.get(img_model, img_model)

        msg = await update.message.reply_text(
            f"🎨 *Membuat gambar...*\n\n"
            f"📝 Prompt: `{prompt}`\n"
            f"🖼 Model: {model_label}\n\n"
            f"⏱ Estimasi: 15–30 detik",
            parse_mode="Markdown",
        )
        try:
            image_url = await generate_image_openrouter(prompt, model=img_model)
            await msg.edit_text(
                f"🎨 *Generate Gambar*\n\n"
                f"{self._render_progress_bar(2, 2, 'Complete ✅')}\n\n"
                f"Gambar selesai dibuat:",
                parse_mode="Markdown"
            )
            await update.message.reply_photo(
                photo=image_url,
                caption=f"🎨 *{prompt[:80]}*\n_Model: {model_label}_",
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.error("Image generation error: %s", e)
            await msg.edit_text(f"❌ Gagal membuat gambar:\n{e}")

    async def img_model_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        img_model = query.data.split("img_", 1)[1]
        context.user_data["img_model"] = img_model
        model_label = OPENROUTER_IMAGE_MODELS.get(img_model, img_model)
        await query.edit_message_text(
            f"✅ Model gambar dipilih: *{model_label}*\n\n"
            f"Sekarang kirim deskripsi gambar:\n"
            f"`/gambar <deskripsi>`",
            parse_mode="Markdown",
        )

    # ──────────────────────────────────────────────────────────────────────
    # CODE EXECUTOR  (/code)
    # ──────────────────────────────────────────────────────────────────────

    async def code_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id if update.effective_user else 0
        if not await check_user_allowed(user_id):
            return
        msg = update.message
        if not msg:
            return

        inline_code = " ".join(context.args).strip() if context.args else ""
        if inline_code:
            await self._run_and_reply(msg, inline_code)
            return

        if context.user_data is not None:
            context.user_data["code_state"] = "waiting"
        await msg.reply_text(
            "🐍 *Python REPL*\n\n"
            "Kirim kode Python yang ingin dijalankan.\n"
            "Kode berjalan di dalam venv proyek dengan akses ke semua modul bot.\n\n"
            "_Contoh:_\n"
            "```python\nfrom src.config import settings\nprint(settings.email_user)\n```",
            parse_mode="Markdown",
        )

    async def _run_and_reply(self, msg, code: str):
        # strip markdown code fences jika ada
        code = code.strip()
        for fence in ("```python", "```"):
            if code.startswith(fence):
                code = code[len(fence):]
        if code.endswith("```"):
            code = code[:-3]
        code = code.strip()

        status = await msg.reply_text("⚙️ Menjalankan kode...")
        result = await execute_python(code, timeout=30)

        if "error" in result:
            await status.edit_text(f"❌ *Error:*\n```\n{result['error']}\n```",
                                   parse_mode="Markdown")
            return

        out = result.get("stdout", "").strip()
        err = result.get("stderr", "").strip()
        rc  = result.get("returncode", 0)

        lines = []
        if out:
            lines.append(f"📤 *Output:*\n```\n{out[:2000]}\n```")
        if err:
            lines.append(f"⚠️ *Stderr:*\n```\n{err[:800]}\n```")
        if not out and not err:
            lines.append("✅ Selesai (tidak ada output)")
        if rc != 0:
            lines.append(f"⚠️ Exit code: `{rc}`")

        await status.edit_text("\n\n".join(lines) or "✅ Selesai",
                               parse_mode="Markdown")

    # ──────────────────────────────────────────────────────────────────────
    # SELF-IMPROVEMENT  (/perbaiki)
    # ──────────────────────────────────────────────────────────────────────

    async def perbaiki_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id if update.effective_user else 0
        if not await check_user_allowed(user_id):
            return
        msg = update.message
        if not msg:
            return

        request = " ".join(context.args).strip() if context.args else ""
        if not request:
            await msg.reply_text(
                "🔧 *Self-Improvement Bot*\n\n"
                "Format: `/perbaiki <deskripsi perubahan>`\n\n"
                "✅ *Contoh:*\n"
                "• `/perbaiki tambahkan perintah /cuaca`\n"
                "• `/perbaiki ubah welcome message di /start`\n"
                "• `/perbaiki tambah model GPT-4 Turbo di OpenRouter`\n\n"
                "AI akan:\n"
                "1. Membaca source code yang relevan\n"
                "2. Membuat improvement script\n"
                "3. Menampilkan preview perubahan\n"
                "4. Menerapkan setelah konfirmasi",
                parse_mode="Markdown",
            )
            return

        await self._generate_improvement(msg, context, request)

    async def _generate_improvement(self, msg, context, request: str):
        from pathlib import Path
        status = await msg.reply_text(
            f"🤖 Menganalisis request: _{request}_\n\n⏳ Membaca source code...",
            parse_mode="Markdown",
        )

        # Baca file-file kunci yang relevan
        root = Path(__file__).parent.parent.parent
        files_context = ""
        key_files = [
            "src/gateway/telegram_handler.py",
            "src/agent/model_router.py",
            "src/config.py",
        ]
        for fp in key_files:
            full = root / fp
            if full.exists():
                content = full.read_text(encoding="utf-8")
                files_context += f"\n\n### {fp} ###\n{content[:6000]}"

        router = await self._ensure_model_router(
            msg.from_user.id if msg.from_user else 0
        )

        await status.edit_text(
            f"🤖 _{request}_\n\n⚙️ AI sedang menulis kode perbaikan...",
            parse_mode="Markdown",
        )

        prompt = f"""Kamu adalah senior Python developer yang membantu memperbaiki bot Telegram bernama "Dewi" milik PT. Arunika Teknologi Global.

Request perubahan: {request}

Source code yang relevan:{files_context}

Tugas: Buat SATU Python script yang:
1. Menggunakan pathlib.Path dan open() untuk membaca dan menulis file
2. Membuat perubahan yang diminta secara tepat dan minimal
3. Tidak menghapus fungsionalitas yang sudah ada
4. Hanya mengubah apa yang diperlukan

Format output HANYA berikan:
PENJELASAN:
<jelaskan singkat apa yang diubah>

SCRIPT:
```python
<python script yang lengkap dan siap dijalankan>
```"""

        try:
            response, _ = await router.call(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=4000,
            )

            # Parse response
            explanation = ""
            script = ""
            if "PENJELASAN:" in response:
                explanation = response.split("PENJELASAN:")[1].split("SCRIPT:")[0].strip()
            if "```python" in response:
                script = response.split("```python")[1].split("```")[0].strip()
            elif "SCRIPT:" in response:
                script = response.split("SCRIPT:")[1].strip()

            if not script:
                await status.edit_text(
                    f"❌ AI gagal menghasilkan script yang valid.\n\nResponse:\n{response[:500]}",
                )
                return

            # Simpan di user_data
            if context.user_data is not None:
                context.user_data["improvement_script"] = script
                context.user_data["improvement_request"] = request

            preview_script = script[:1500] + ("\n..." if len(script) > 1500 else "")
            keyboard = [
                [InlineKeyboardButton("✅ Terapkan & Restart Bot", callback_data="improve_apply")],
                [InlineKeyboardButton("🔍 Jalankan Test Dulu", callback_data="improve_test")],
                [InlineKeyboardButton("❌ Batal", callback_data="improve_cancel")],
            ]

            await status.edit_text(
                f"🔧 *Improvement Plan*\n\n"
                f"📋 *Request:* _{request}_\n\n"
                f"💡 *Penjelasan:*\n{explanation[:400]}\n\n"
                f"📝 *Script ({len(script)} chars):*\n"
                f"```python\n{preview_script}\n```",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown",
            )

        except Exception as e:
            logger.exception("Improvement generation error: %s", e)
            await status.edit_text(f"❌ Gagal generate improvement: {e}")

    async def improve_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        if not query or not query.data or context.user_data is None:
            return
        await query.answer()
        data = query.data
        ud = context.user_data
        script  = ud.get("improvement_script", "")
        request = ud.get("improvement_request", "")

        if data == "improve_cancel":
            ud.pop("improvement_script", None)
            ud.pop("improvement_request", None)
            await query.edit_message_text("❌ Improvement dibatalkan.")

        elif data == "improve_test":
            if not script:
                await query.edit_message_text("❌ Tidak ada script.")
                return
            await query.edit_message_text("🧪 Menjalankan script dalam mode test (dry run)...")
            # Jalankan tapi tandai DRY_RUN=1 agar script bisa cek
            test_script = f"import os; os.environ['DRY_RUN']='1'\n{script}"
            result = await execute_python(test_script, timeout=30)
            out = result.get("stdout", "")
            err = result.get("stderr", "")
            success = result.get("success", False)
            icon = "✅" if success else "❌"
            keyboard = [
                [InlineKeyboardButton("✅ Terapkan & Restart", callback_data="improve_apply")],
                [InlineKeyboardButton("❌ Batal", callback_data="improve_cancel")],
            ]
            await query.edit_message_text(
                f"{icon} *Test Result:*\n"
                f"```\n{(out or err or 'no output')[:1500]}\n```",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown",
            )

        elif data == "improve_apply":
            if not script:
                await query.edit_message_text("❌ Tidak ada script.")
                return
            await query.edit_message_text(
                f"⚙️ Menerapkan perubahan: _{request}_\n\nMohon tunggu...",
                parse_mode="Markdown",
            )
            result = await apply_improvement(script, timeout=60)
            if not result.get("success"):
                err = result.get("stderr") or result.get("error") or "unknown error"
                await query.edit_message_text(
                    f"❌ *Gagal menerapkan:*\n```\n{err[:1000]}\n```",
                    parse_mode="Markdown",
                )
                return

            ud.pop("improvement_script", None)
            ud.pop("improvement_request", None)
            await query.edit_message_text(
                f"✅ *Perubahan berhasil diterapkan!*\n\n"
                f"📋 _{request}_\n\n"
                f"🔄 Bot akan restart dalam 2 detik...",
                parse_mode="Markdown",
            )

            import asyncio as _asyncio
            await _asyncio.sleep(2)
            restart_bot()   # exit process → start.bat akan restart otomatis

    # ──────────────────────────────────────────────────────────────────────
    # SURAT
    # ──────────────────────────────────────────────────────────────────────

    async def _handle_surat_state(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        surat_state: str,
        user_message: str,
    ):
        msg = update.message
        if not msg or context.user_data is None:
            return
        ud = context.user_data
        draft: dict = ud.setdefault("surat_draft", {})

        if surat_state == "surat_brief":
            ud["surat_state"] = None
            user_id = update.effective_user.id if update.effective_user else 0
            await msg.chat.send_action("typing")
            status = await msg.reply_text(
                "🤖 AI sedang menyusun surat...\n"
                f"{self._render_progress_bar(1, 4, 'Membaca riset sebelumnya')}\n"
                "⏱ Estimasi 15-20 detik",
                parse_mode="Markdown",
            )
            router = await self._ensure_model_router(user_id)

            riset_context = await self._get_research_context(user_id, user_message)

            await status.edit_text(
                "🤖 AI sedang menyusun surat...\n"
                f"{self._render_progress_bar(2, 4, 'Menyusun draft surat')}\n"
                "⏱ Estimasi 15-20 detik",
                parse_mode="Markdown",
            )

            riset_block = (
                f"\n\nRISET / KONTEKS SEBELUMNYA TENTANG PENERIMA "
                f"(WAJIB dijadikan dasar isi surat — sebut data konkret, "
                f"angka, profil, fakta yang relevan):\n{riset_context}\n"
            ) if riset_context else ""

            ai_prompt = f"""Kamu adalah Corporate Secretary PT. Arunika Teknologi Global (ATG).
Buat surat resmi profesional dalam Bahasa Indonesia berdasarkan brief berikut.

Brief dari pengguna: {user_message}{riset_block}

INSTRUKSI PENTING:
1. WAJIB pakai fakta dari RISET di atas (jika ada) — sebut nama institusi resmi,
   data konkret, profil, kebutuhan/pain-point yang sudah diidentifikasi.
2. Jangan pakai placeholder seperti "[Nama Yayasan]" / "[Isi disini]" —
   isi dengan data nyata dari riset atau brief.
3. Isi surat minimum 3 paragraf substansial (bukan template kosong).

FORMAT BALASAN - WAJIB PERSIS seperti ini, tidak lebih tidak kurang:

TUJUAN_NAMA: [nama lengkap penerima — ambil dari riset/brief, BUKAN placeholder]
TUJUAN_JABATAN: [jabatan penerima, contoh: Ketua Yayasan / Direktur Utama]
TUJUAN_INSTITUSI: [nama resmi institusi penerima — ambil dari riset]
TUJUAN_KOTA: [kota penerima — ambil dari riset, default: Tempat]
PERIHAL: [judul/perihal surat, singkat dan jelas]
LAMPIRAN: [-]
PENANDATANGAN_NAMA: [Ir. Rachmat Ari Kusumanto]
PENANDATANGAN_JABATAN: [Direktur]
ISI_SURAT:
[Tulis isi surat 3-4 paragraf profesional yang merujuk DATA NYATA dari riset.
Paragraf 1: pembuka + apresiasi/pengantar (sebut fakta institusi penerima).
Paragraf 2: maksud surat + solusi/penawaran ATG yang sesuai pain-point penerima.
Paragraf 3: detail benefit + ajakan tindak lanjut.
Jangan tulis salam (Assalamualaikum dll), bismillah, atau tanda tangan —
sudah ada di template. Langsung tulis paragraf isi saja.]
SELESAI"""

            try:
                response, _ = await router.call(
                    messages=[{"role": "user", "content": ai_prompt}],
                    temperature=0.3,
                    max_tokens=2000,
                )
                try:
                    await status.edit_text(
                        "🤖 AI sedang menyusun surat...\n"
                        f"{self._render_progress_bar(3, 4, 'Parsing & validasi')}\n"
                        "⏱ Hampir selesai...",
                        parse_mode="Markdown",
                    )
                except Exception:
                    pass

                # ── Parsing robust: coba beberapa variasi key ─────────────
                def _extract(text: str, *keys) -> str:
                    for k in keys:
                        for line in text.splitlines():
                            stripped = line.strip()
                            if stripped.upper().startswith(k.upper() + ":"):
                                val = stripped[len(k)+1:].strip()
                                if val:
                                    return val
                    return ""

                # Isi surat: ambil antara ISI_SURAT: dan SELESAI (atau akhir teks)
                def _extract_isi(text: str) -> str:
                    markers_start = ["ISI_SURAT:", "ISI:"]
                    markers_end   = ["SELESAI", "---"]
                    body = ""
                    for ms in markers_start:
                        if ms in text.upper():
                            idx = text.upper().index(ms)
                            body = text[idx + len(ms):].strip()
                            break
                    if not body:
                        # fallback: pakai semua teks setelah baris ke-10
                        lines = text.strip().splitlines()
                        body = "\n".join(lines[9:]).strip() if len(lines) > 9 else text
                    # potong di marker akhir
                    for me in markers_end:
                        if me in body.upper():
                            body = body[:body.upper().index(me)].strip()
                    return body.strip()

                perihal   = _extract(response, "PERIHAL")
                tujuan_n  = _extract(response, "TUJUAN_NAMA", "KEPADA_NAMA", "NAMA")
                tujuan_j  = _extract(response, "TUJUAN_JABATAN", "JABATAN")
                tujuan_i  = _extract(response, "TUJUAN_INSTITUSI", "INSTITUSI", "PERUSAHAAN")
                tujuan_k  = _extract(response, "TUJUAN_KOTA", "KOTA") or "Tempat"
                ttd_nama  = _extract(response, "PENANDATANGAN_NAMA") or "Ir. Rachmat Ari Kusumanto"
                ttd_jab   = _extract(response, "PENANDATANGAN_JABATAN") or "Direktur"
                isi       = _extract_isi(response)

                # ── Fallback jika perihal kosong ──────────────────────────
                if not perihal:
                    # coba ambil dari brief user
                    words = user_message.split()[:8]
                    perihal = " ".join(words).title()

                # ── Validasi minimum ──────────────────────────────────────
                if not isi or len(isi) < 50:
                    await status.edit_text(
                        "⚠️ AI tidak menghasilkan isi surat yang memadai.\n\n"
                        "Coba deskripsikan lebih detail, contoh:\n"
                        "_'Buat surat kerjasama kepada Direktur PT X mengenai implementasi AI di bidang Y'_\n\n"
                        "Atau gunakan /sek → Tulis Manual",
                        parse_mode="Markdown",
                    )
                    return

                draft.update({
                    "tujuan_nama":           tujuan_n,
                    "tujuan_jabatan":        tujuan_j,
                    "tujuan_institusi":      tujuan_i,
                    "tujuan_kota":           tujuan_k,
                    "perihal":               perihal,
                    "lampiran":              "-",
                    "penandatangan_nama":    ttd_nama,
                    "penandatangan_jabatan": ttd_jab,
                    "isi":                   isi,
                })
                await status.edit_text(
                    "📄 Draft surat selesai ✅\n"
                    f"{self._render_progress_bar(4, 4, 'Complete')}\n"
                    "Menampilkan preview...",
                    parse_mode="Markdown",
                )
                await self._show_surat_preview(update, context, draft)

            except Exception as e:
                logger.exception("Surat AI draft error: %s", e)
                await status.edit_text(
                    f"❌ Gagal menyusun surat: {type(e).__name__}: {e}\n\n"
                    "Coba lagi atau gunakan /sek → Tulis Manual"
                )

        elif surat_state == "surat_tujuan":
            draft["tujuan_nama"] = user_message
            ud["surat_state"] = "surat_jabatan"
            await msg.reply_text(
                f"✅ Kepada: *{user_message}*\n\n"
                "Masukkan *jabatan* penerima:\n_Contoh: Direktur Utama, Kepala Dinas_",
                parse_mode="Markdown",
            )

        elif surat_state == "surat_jabatan":
            draft["tujuan_jabatan"] = user_message
            ud["surat_state"] = "surat_institusi"
            await msg.reply_text(
                f"✅ Jabatan: *{user_message}*\n\n"
                "Masukkan *nama institusi/perusahaan* penerima:",
                parse_mode="Markdown",
            )

        elif surat_state == "surat_institusi":
            draft["tujuan_institusi"] = user_message
            ud["surat_state"] = "surat_perihal"
            await msg.reply_text(
                f"✅ Institusi: *{user_message}*\n\n"
                "Masukkan *perihal* surat:\n_Contoh: Penawaran Kerjasama Pengembangan AI_",
                parse_mode="Markdown",
            )

        elif surat_state == "surat_perihal":
            draft["tujuan_perihal"] = user_message
            draft["perihal"] = user_message
            ud["surat_state"] = "surat_isi"
            await msg.reply_text(
                f"✅ Perihal: *{user_message}*\n\n"
                "📝 Tulis *isi surat* (beberapa paragraf).\n"
                "_Jangan perlu salam pembuka/penutup — sudah ada di template._",
                parse_mode="Markdown",
            )

        elif surat_state == "surat_isi":
            draft["isi"] = user_message
            ud["surat_state"] = None
            if not draft.get("penandatangan_nama"):
                draft["penandatangan_nama"] = "Ir. Rachmat Ari Kusumanto"
                draft["penandatangan_jabatan"] = "Direktur"
            await self._show_surat_preview(update, context, draft)

        elif surat_state == "surat_email_to":
            # Setelah PDF sudah dibuat, user memasukkan email tujuan
            ud["surat_state"] = None
            pdf_path = draft.get("pdf_path", "")
            if not pdf_path:
                await msg.reply_text("❌ PDF belum dibuat. Mulai ulang /sek")
                return
            status = await msg.reply_text("📤 Mengirim surat via email...")
            result = await send_email(
                to=user_message,
                subject=f"[Surat ATG] {draft.get('perihal', '')}",
                body=(
                    f"Assalamu'alaikum Warahmatullahi Wabarakatuh,\n\n"
                    f"Terlampir surat resmi dari PT. Arunika Teknologi Global.\n\n"
                    f"Perihal: {draft.get('perihal', '')}\n\n"
                    f"Wassalamu'alaikum Warahmatullahi Wabarakatuh.\n\n"
                    f"Hormat kami,\nPT. Arunika Teknologi Global\n"
                    f"{draft.get('penandatangan_nama', '')}\n"
                    f"{draft.get('penandatangan_jabatan', '')}"
                ),
                attachment_path=pdf_path,
            )
            if "error" in result:
                await status.edit_text(f"❌ Gagal kirim email:\n`{result['error']}`",
                                       parse_mode="Markdown")
            else:
                await status.edit_text(
                    f"✅ *Surat berhasil dikirim!*\n\n"
                    f"📧 Kepada: `{user_message}`\n"
                    f"📌 Perihal: `{draft.get('perihal', '')}`",
                    parse_mode="Markdown",
                )

    async def _handle_presentasi_state(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        presentasi_state: str,
        user_message: str,
    ):
        """Handle presentation creation flow with Claude Skills."""
        if not update.message or not context.user_data:
            return
        msg = update.message
        ud = context.user_data
        user_id = update.effective_user.id if update.effective_user else 0

        if presentasi_state == "presentasi_topik":
            ud["presentasi_state"] = None
            ud["presentasi_draft"] = {"topik": user_message}

            status = await msg.reply_text(
                "⏳ Membuat outline presentasi...\n"
                f"{self._render_progress_bar(1, 3, 'Membaca riset sebelumnya')}",
                parse_mode="Markdown",
            )

            try:
                riset_context = await self._get_research_context(user_id, user_message)

                try:
                    await status.edit_text(
                        "⏳ Membuat outline presentasi...\n"
                        f"{self._render_progress_bar(2, 3, 'Menyusun outline dengan AI')}",
                        parse_mode="Markdown",
                    )
                except Exception:
                    pass

                riset_block = (
                    f"\n\nRISET / KONTEKS SEBELUMNYA (WAJIB dijadikan dasar slide — "
                    f"sebut data konkret, angka, profil, fakta yang relevan):\n"
                    f"{riset_context}\n"
                ) if riset_context else ""

                presentation_prompt = f"""Buatkan outline presentasi profesional (PowerPoint/slide):

Topik: {user_message}{riset_block}

INSTRUKSI:
1. WAJIB pakai fakta dari RISET di atas (jika ada) — sebut data konkret,
   angka, profil, pain-point, peluang yang sudah teridentifikasi.
2. Jangan pakai placeholder generik — isi setiap slide dengan substansi nyata.

STRUKTUR SLIDE:
- Slide 1: Cover (judul + subjudul + tanggal)
- Slide 2: Executive Summary (3-4 bullet inti)
- Slide 3: Latar Belakang / Konteks (data dari riset)
- Slide 4: Pain Point / Masalah (spesifik, terukur)
- Slide 5: Solusi yang Ditawarkan
- Slide 6: Benefit & Value (kuantitatif jika bisa)
- Slide 7: Timeline / Roadmap
- Slide 8: Investasi / Cost (jika relevan)
- Slide 9: Next Steps / Call-to-Action
- Slide 10: Penutup / Kontak

Untuk SETIAP slide tulis:
*Slide N — [Judul]*
• Bullet point 1 (substansi konkret)
• Bullet point 2
_Catatan presenter: ..._

Format output dengan asterisk tunggal untuk bold dan bullet •.
JANGAN pakai `## heading`, `**bold**`, atau `| pipe table |`."""

                result = await self.agent.chat(
                    user_id=user_id,
                    user_message=presentation_prompt,
                )

                outline = str(result) if result else "Gagal generate outline"
                ud["presentasi_draft"]["outline"] = outline[:2000]  # simpan 2000 char pertama

                keyboard = [
                    [InlineKeyboardButton("✅ Terima", callback_data="presentasi_accept")],
                    [InlineKeyboardButton("♻️ Buat Ulang", callback_data="presentasi_retry")],
                    [InlineKeyboardButton("❌ Batal", callback_data="presentasi_cancel")],
                ]

                preview = outline[:500] + ("..." if len(outline) > 500 else "")
                await status.edit_text(
                    f"📊 *Outline Presentasi*\n\n"
                    f"🎯 Topik: _{user_message}_\n\n"
                    f"📝 *Preview:*\n{preview}\n\n"
                    f"Pilih tindakan:",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown",
                )

            except Exception as e:
                logger.exception("Presentasi generation error: %s", e)
                await status.edit_text(
                    f"❌ Gagal membuat outline:\n`{e}`\n\n"
                    "Coba lagi dengan /sek",
                    parse_mode="Markdown"
                )
                ud["presentasi_state"] = None

    async def _handle_surat_gen_state(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        surat_gen_state: str,
        user_message: str,
    ):
        """Handle state machine untuk Smart Surat Generator (edit & email)."""
        msg = update.message
        if not msg or context.user_data is None:
            return

        ud = context.user_data
        surat_gen = ud.get("surat_generated", {})

        if surat_gen_state == "editing":
            # User masukkan editan untuk surat
            ud["surat_gen_state"] = None
            original_content = surat_gen.get("content", "")

            # Generate ulang surat dengan editan user
            source_result = ud.get("surat_source_result", "")
            template_type = ud.get("surat_template_type", "proposal")
            user_id = update.effective_user.id if update.effective_user else 0

            await msg.chat.send_action("typing")
            status = await msg.reply_text("🔄 Claude sedang merevisi surat berdasarkan masukan Anda...")

            try:
                router = await self._ensure_model_router(user_id)

                async def progress_callback(text: str):
                    try:
                        await status.edit_text(f"🔄 {text}")
                    except Exception:
                        pass

                prompt = f"""Revisi surat berikut berdasarkan masukan user.

SURAT ORIGINAL:
{original_content}

MASUKAN USER:
{user_message}

INSTRUKSI:
1. Terapkan semua masukan user pada surat
2. Pertahankan struktur dan format profesional
3. Jangan ubah tujuan surat, hanya detail/konten
4. Kirim hanya surat yang sudah direvisi (tanpa penjelasan)"""

                result = await self.hermes.run(
                    task=prompt,
                    router=router,
                    on_progress=progress_callback,
                    user_id=user_id,
                )

                surat_gen["content"] = result
                ud["surat_generated"] = surat_gen
                await status.edit_text("✅ Revisi surat selesai!")

                # Tampilkan surat yang sudah direvisi dengan opsi download/edit
                keyboard = [
                    [InlineKeyboardButton("📥 Download PDF", callback_data="surat_dl_pdf"),
                     InlineKeyboardButton("📝 Edit Lagi", callback_data="surat_edit")],
                    [InlineKeyboardButton("💾 Kirim Email", callback_data="surat_send_email"),
                     InlineKeyboardButton("❌ Batal", callback_data="surat_cancel")],
                ]

                preview = (result[:1500] + "\n\n...[terpotong]") if len(result) > 1500 else result
                await msg.reply_text(
                    f"✅ *Surat Direvisi*\n\n"
                    f"```\n{preview}\n```",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown",
                )
            except Exception as e:
                logger.exception("Surat revision error: %s", e)
                await status.edit_text(f"❌ Gagal merevisi surat: {e}", parse_mode="Markdown")

    async def _handle_surat_email_state(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        surat_email_state: str,
        user_message: str,
    ):
        """Handle email sending untuk Smart Surat Generator."""
        msg = update.message
        if not msg or context.user_data is None:
            return

        ud = context.user_data
        surat_gen = ud.get("surat_generated", {})

        if surat_email_state == "email_to":
            ud["surat_email_state"] = None
            to_email = user_message.strip()

            if not to_email or "@" not in to_email:
                await msg.reply_text(
                    "❌ Format email tidak valid. Silakan coba lagi dengan format: nama@domain.com"
                )
                return

            await msg.chat.send_action("typing")
            status = await msg.reply_text("📧 Membuat PDF dan mengirim email...")

            try:
                # Generate PDF
                perihal = surat_gen.get("template", "Surat").upper()
                pdf_path = self.surat_gen.generate_pdf(
                    perihal=perihal,
                    isi=surat_gen.get("content", ""),
                )

                # Gunakan email sender untuk kirim surat
                result = await send_email(
                    to=to_email,
                    subject=f"Surat {perihal} — PT. Arunika Teknologi Global",
                    body=f"Berikut adalah surat {perihal.lower()} yang diminta.\n\nDikutrimkan via PT. Arunika Teknologi Global.",
                    attachment_path=pdf_path,
                )

                await status.edit_text("📧 Email surat selesai dikirim ✅")

                if "error" in result:
                    await msg.reply_text(
                        f"❌ Gagal mengirim email: {result['error']}",
                        parse_mode="Markdown"
                    )
                else:
                    await msg.reply_text(
                        f"✅ *Email Terkirim!*\n\n"
                        f"📧 Kepada: `{to_email}`\n"
                        f"📄 File: Surat_{perihal}.pdf\n\n"
                        "Surat profesional dengan letterhead ATG telah dikirimkan.",
                        parse_mode="Markdown"
                    )
                    # Cleanup
                    ud.pop("surat_source_result", None)
                    ud.pop("surat_generated", None)
                    ud.pop("surat_template_type", None)

            except Exception as e:
                logger.exception("Surat email error: %s", e)
                await status.edit_text(f"❌ Gagal mengirim email: {e}", parse_mode="Markdown")

    async def _show_surat_preview(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        draft: dict,
    ):
        if not update.message or context.user_data is None:
            return
        ud = context.user_data
        isi_preview = (draft.get("isi", "") or "")[:400]
        if len(draft.get("isi", "")) > 400:
            isi_preview += "..."

        text = (
            f"📄 *Preview Surat*\n\n"
            f"📥 Kepada: *{draft.get('tujuan_jabatan', '')}* "
            f"— {draft.get('tujuan_institusi', '')}\n"
            f"📌 Perihal: *{draft.get('perihal', '')}*\n"
            f"✍️ Ttd: {draft.get('penandatangan_nama', '')} "
            f"({draft.get('penandatangan_jabatan', '')})\n\n"
            f"📝 *Cuplikan Isi:*\n_{isi_preview}_\n\n"
            f"Pilih tindakan:"
        )
        keyboard = [
            [InlineKeyboardButton("📄 Download PDF", callback_data="surat_download")],
            [InlineKeyboardButton("📧 Kirim via Email", callback_data="surat_email")],
            [InlineKeyboardButton("❌ Batal", callback_data="surat_batal")],
        ]
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    async def surat_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        if not query or not query.data or context.user_data is None:
            return
        await query.answer()
        data = query.data
        ud = context.user_data
        draft: dict = ud.get("surat_draft", {})

        if data == "surat_download":
            if not draft.get("perihal") or not draft.get("isi"):
                await query.edit_message_text(
                    "⚠️ *Draft surat hilang* — kemungkinan bot baru direstart.\n\n"
                    "Ketik /sek → Buat Surat untuk memulai ulang.",
                    parse_mode="Markdown",
                )
                return
            await query.edit_message_text("⏳ Membuat PDF surat...")
            try:
                pdf_path = await self._generate_surat_pdf(draft)
                draft["pdf_path"] = pdf_path
                await query.delete_message()
                with open(pdf_path, "rb") as f:
                    perihal_safe = draft.get("perihal", "surat")[:40]
                    if query.message and query.message.chat:
                        await query.message.chat.send_document(
                            document=f,
                            filename=f"Surat ATG - {perihal_safe}.pdf",
                            caption=(
                                f"📄 *Surat Resmi ATG*\n"
                                f"📌 Perihal: _{draft.get('perihal', '')}_\n\n"
                                f"Gunakan /sek jika ingin kirim via email."
                            ),
                            parse_mode="Markdown",
                        )
            except Exception as e:
                logger.exception("Surat PDF error: %s", e)
                await query.edit_message_text(f"❌ Gagal membuat PDF:\n{e}")

        elif data == "surat_email":
            if not draft.get("perihal") or not draft.get("isi"):
                await query.edit_message_text(
                    "⚠️ *Draft surat hilang* — kemungkinan bot baru direstart.\n\n"
                    "Ketik /sek → Buat Surat untuk memulai ulang.",
                    parse_mode="Markdown",
                )
                return
            # Generate PDF dulu jika belum ada
            if not draft.get("pdf_path"):
                await query.edit_message_text("⏳ Membuat PDF...")
                try:
                    pdf_path = await self._generate_surat_pdf(draft)
                    draft["pdf_path"] = pdf_path
                except Exception as e:
                    await query.edit_message_text(f"❌ Gagal membuat PDF:\n{e}")
                    return
            ud["surat_state"] = "surat_email_to"
            await query.edit_message_text(
                "📧 *Kirim Surat via Email*\n\n"
                "Masukkan *alamat email* penerima:",
                parse_mode="Markdown",
            )

        elif data == "surat_batal":
            ud.pop("surat_draft", None)
            ud.pop("surat_state", None)
            await query.edit_message_text("❌ Pembuatan surat dibatalkan.")

    async def _generate_surat_pdf(self, draft: dict) -> str:
        """Run blocking PDF generation in thread executor."""
        import asyncio
        def _build():
            return self.surat_gen.generate_pdf(
                perihal=draft.get("perihal", ""),
                isi=draft.get("isi", ""),
                tujuan_nama=draft.get("tujuan_nama", ""),
                tujuan_jabatan=draft.get("tujuan_jabatan", ""),
                tujuan_institusi=draft.get("tujuan_institusi", ""),
                tujuan_kota=draft.get("tujuan_kota", "Tempat"),
                lampiran=draft.get("lampiran", "-"),
                penandatangan_nama=draft.get("penandatangan_nama", ""),
                penandatangan_jabatan=draft.get("penandatangan_jabatan", ""),
            )
        return await asyncio.to_thread(_build)

    # ──────────────────────────────────────────────────────────────────────
    # EMAIL
    # ──────────────────────────────────────────────────────────────────────

    async def email_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not await check_user_allowed(user_id):
            return

        if not settings.email_user or not settings.email_password:
            await update.message.reply_text(
                "❌ Konfigurasi email belum diatur di .env\n"
                "Tambahkan EMAIL_USER dan EMAIL_PASSWORD"
            )
            return

        keyboard = [
            [InlineKeyboardButton("✍️ Tulis Manual", callback_data="email_manual")],
            [InlineKeyboardButton("🤖 Bantu AI Draft", callback_data="email_ai")],
            [InlineKeyboardButton("🔌 Test Koneksi SMTP", callback_data="email_test")],
        ]
        await update.message.reply_text(
            f"📧 *Kirim Email*\n\n"
            f"📤 Pengirim: `{settings.email_user}`\n"
            f"🌐 SMTP: `{settings.email_host}:{settings.email_port}`\n\n"
            "Pilih cara penulisan:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    async def _handle_email_state(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        email_state: str,
        user_message: str,
    ):
        msg = update.message
        if not msg or not context.user_data:
            return
        ud = context.user_data
        draft: dict = ud.setdefault("email_draft", {})

        if email_state == "email_to":
            draft["to"] = user_message
            ud["email_state"] = "email_subject"
            await msg.reply_text(
                f"✅ Penerima: `{user_message}`\n\n📌 Masukkan *subjek* email:",
                parse_mode="Markdown",
            )

        elif email_state == "email_subject":
            draft["subject"] = user_message
            ud["email_state"] = "email_body"
            await msg.reply_text(
                f"✅ Subjek: `{user_message}`\n\n📝 Tulis *isi* surat/email, lalu kirim:",
                parse_mode="Markdown",
            )

        elif email_state == "email_body":
            draft["body"] = user_message
            ud["email_state"] = None
            await self._show_email_preview(update, context, draft)

        elif email_state == "email_ai_brief":
            ud["email_state"] = None
            user_id = update.effective_user.id if update.effective_user else 0
            await msg.chat.send_action("typing")
            status = await msg.reply_text("🤖 AI sedang membuat draft surat...")
            router = await self._ensure_model_router(user_id)

            ai_prompt = (
                "Buat draft email profesional dalam Bahasa Indonesia berdasarkan brief berikut.\n\n"
                f"Brief: {user_message}\n\n"
                f"Pengirim: {settings.email_user} (Corporate Secretary, PT. Arunika Teknologi Global)\n\n"
                "Balas HANYA dalam format ini (tanpa tambahan apapun):\n"
                "KEPADA: <alamat email atau nama penerima>\n"
                "SUBJEK: <subjek email>\n"
                "ISI:\n<isi email lengkap dan profesional>"
            )
            try:
                response, _ = await router.call(
                    messages=[{"role": "user", "content": ai_prompt}],
                    temperature=0.4,
                    max_tokens=2000,
                )
                to_val, subject_val = "", ""
                in_body = False
                body_lines: list[str] = []
                for line in response.strip().splitlines():
                    ul = line.upper()
                    if ul.startswith("KEPADA:"):
                        to_val = line.split(":", 1)[1].strip()
                    elif ul.startswith("SUBJEK:"):
                        subject_val = line.split(":", 1)[1].strip()
                    elif ul.startswith("ISI:"):
                        in_body = True
                    elif in_body:
                        body_lines.append(line)

                draft["to"] = to_val
                draft["subject"] = subject_val
                draft["body"] = "\n".join(body_lines).strip()
                await status.edit_text("📧 Draft email selesai ✅\nMenampilkan preview...")
                await self._show_email_preview(update, context, draft, ai_generated=True)
            except Exception as e:
                await status.edit_text(f"❌ Gagal membuat draft AI: {e}")

    async def _show_email_preview(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        draft: dict,
        ai_generated: bool = False,
    ):
        if not update.message:
            return
        header = "🤖 *AI Draft Selesai — Preview Email*" if ai_generated else "📧 *Preview Email*"
        body_preview = draft.get("body", "")
        if len(body_preview) > 600:
            body_preview = body_preview[:600] + "\n_...( terpotong )_"
        text = (
            f"{header}\n\n"
            f"📤 Dari: `{settings.email_user}`\n"
            f"📥 Kepada: `{draft.get('to', '-')}`\n"
            f"📌 Subjek: `{draft.get('subject', '-')}`\n\n"
            f"📝 *Isi:*\n{body_preview}\n\n"
            "Kirim email ini?"
        )
        keyboard = [
            [InlineKeyboardButton("✅ Kirim Sekarang", callback_data="email_send")],
            [InlineKeyboardButton("✏️ Edit Penerima", callback_data="email_edit_to")],
            [InlineKeyboardButton("❌ Batal", callback_data="email_cancel")],
        ]
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    async def email_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        if not query or not query.data or not context.user_data:
            return
        await query.answer()
        data = query.data
        ud = context.user_data
        draft: dict = ud.setdefault("email_draft", {})

        if data == "email_manual":
            ud["email_state"] = "email_to"
            ud["email_draft"] = {}
            await query.edit_message_text(
                "✍️ *Kirim Email Manual*\n\n"
                "Masukkan *alamat email penerima*:\n"
                "_Contoh: direktur@perusahaan.com_\n"
                "_Beberapa penerima pisahkan dengan koma_",
                parse_mode="Markdown",
            )

        elif data == "email_ai":
            ud["email_state"] = "email_ai_brief"
            ud["email_draft"] = {}
            await query.edit_message_text(
                "🤖 *AI Draft Surat*\n\n"
                "Jelaskan surat yang ingin dikirim:\n\n"
                "_Contoh: Surat penawaran kerjasama kepada PT Maju Mundur "
                "mengenai implementasi sistem AI untuk divisi HR_",
                parse_mode="Markdown",
            )

        elif data == "email_test":
            await query.edit_message_text("🔌 Menguji koneksi SMTP...")
            result = await test_smtp_connection()
            if "error" in result:
                await query.edit_message_text(
                    f"❌ *Koneksi gagal!*\n\n`{result['error']}`",
                    parse_mode="Markdown",
                )
            else:
                await query.edit_message_text(
                    f"✅ *Koneksi SMTP berhasil!*\n\n"
                    f"🌐 Host: `{result['host']}`\n"
                    f"👤 User: `{result['user']}`\n\n"
                    "Siap mengirim email.",
                    parse_mode="Markdown",
                )

        elif data == "email_send":
            if not draft.get("to") or not draft.get("subject") or not draft.get("body"):
                await query.edit_message_text("❌ Draft tidak lengkap. Mulai ulang dengan /email")
                return
            await query.edit_message_text("📤 Mengirim email...")
            result = await send_email(
                to=draft["to"],
                subject=draft["subject"],
                body=draft["body"],
            )
            if "error" in result:
                await query.edit_message_text(
                    f"❌ *Gagal mengirim email:*\n\n`{result['error']}`",
                    parse_mode="Markdown",
                )
            else:
                await query.edit_message_text(
                    f"✅ *Email berhasil dikirim!*\n\n"
                    f"📤 Dari: `{settings.email_user}`\n"
                    f"📥 Kepada: `{draft['to']}`\n"
                    f"📌 Subjek: `{draft['subject']}`",
                    parse_mode="Markdown",
                )
            ud.pop("email_draft", None)
            ud.pop("email_state", None)

        elif data == "email_edit_to":
            ud["email_state"] = "email_to"
            await query.edit_message_text(
                "✏️ *Edit Penerima*\n\nMasukkan alamat email penerima yang baru:",
                parse_mode="Markdown",
            )

        elif data == "email_cancel":
            ud.pop("email_draft", None)
            ud.pop("email_state", None)
            await query.edit_message_text("❌ Pengiriman email dibatalkan.")

    async def module_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        callback_data = query.data

        # ── R&D callbacks (fully implemented) ────────────────────────────
        if callback_data == "rnd_riset":
            context.user_data["rnd_state"] = "riset"
            await query.edit_message_text(
                "🔍 *Riset Calon Mitra*\n\n"
                "Masukkan nama perusahaan atau website yang ingin diriset:\n"
                "_Contoh: Tokopedia, gojek.com, PT Telkom Indonesia_",
                parse_mode="Markdown"
            )

        elif callback_data == "rnd_swot":
            context.user_data["rnd_state"] = "swot"
            await query.edit_message_text(
                "📈 *Analisis SWOT*\n\n"
                "Masukkan subjek yang ingin dianalisis:\n"
                "_Contoh: Gojek, Pasar AI Indonesia, Produk ATG di sektor kesehatan_",
                parse_mode="Markdown"
            )

        elif callback_data == "rnd_proposal":
            context.user_data["rnd_state"] = "proposal_step1"
            await query.edit_message_text(
                "📋 *Buat Proposal Kemitraan*\n\n"
                "Langkah 1/2 — Masukkan nama perusahaan mitra:\n"
                "_Contoh: PT Bank Mandiri, Shopee Indonesia, RS Pondok Indah_",
                parse_mode="Markdown"
            )

        elif callback_data == "rnd_tech":
            context.user_data["rnd_state"] = "tech"
            await query.edit_message_text(
                "🔬 *Riset Teknologi*\n\n"
                "Masukkan topik teknologi yang ingin diriset:\n"
                "_Contoh: Agentic AI 2025, RAG untuk enterprise, Computer Vision di manufaktur_",
                parse_mode="Markdown"
            )

        elif callback_data == "rnd_scrape":
            context.user_data["rnd_state"] = "scrape"
            await query.edit_message_text(
                "🕷️ *Scrape Website*\n\n"
                "Masukkan URL website yang ingin di-scrape:\n"
                "_Contoh: https://tokopedia.com/about_",
                parse_mode="Markdown"
            )

        # ── Sekretaris callbacks ──────────────────────────────────────────
        elif callback_data == "sek_surat":
            keyboard = [
                [InlineKeyboardButton("🤖 AI Draft Otomatis", callback_data="surat_mode_ai")],
                [InlineKeyboardButton("✍️ Tulis Manual", callback_data="surat_mode_manual")],
            ]
            await query.edit_message_text(
                "📄 *Buat Surat Resmi ATG*\n\n"
                "Surat akan dicetak dengan letterhead & logo PT. Arunika Teknologi Global.\n\n"
                "Pilih cara penulisan:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown",
            )

        elif callback_data == "surat_mode_ai":
            if context.user_data is not None:
                context.user_data["surat_state"] = "surat_brief"
                context.user_data["surat_draft"] = {}
            await query.edit_message_text(
                "🤖 *AI Draft Surat*\n\n"
                "Jelaskan surat yang ingin dibuat:\n\n"
                "✅ *Contoh:*\n"
                "• _Surat penawaran kerjasama dengan RS Hasan Sadikin mengenai sistem AI_\n"
                "• _Surat undangan seminar AI untuk instansi pemerintah di Bandung_\n"
                "• _Surat permohonan dukungan kepada Dinas Kominfo Jawa Barat_",
                parse_mode="Markdown",
            )

        elif callback_data == "surat_mode_manual":
            if context.user_data is not None:
                context.user_data["surat_state"] = "surat_tujuan"
                context.user_data["surat_draft"] = {}
            await query.edit_message_text(
                "✍️ *Buat Surat Manual*\n\n"
                "Masukkan *nama lengkap* penerima surat:\n"
                "_Contoh: Dr. Ahmad Budi Santoso_",
                parse_mode="Markdown",
            )

        elif callback_data == "sek_presentasi":
            if context.user_data is not None:
                context.user_data["presentasi_state"] = "presentasi_topik"

            skill_hint = self._get_presentation_skill_hint()

            await query.edit_message_text(
                "📊 *Buat Bahan Presentasi*\n\n"
                "Deskripsikan presentasi yang ingin dibuat:\n\n"
                "✅ *Contoh:*\n"
                "• _Presentasi Strategi Digital Transformation 2025 untuk board meeting_\n"
                "• _Slide produk AI tools untuk client pitch meeting_\n"
                "• _Presentasi training tim development tentang clean code_\n\n"
                f"{skill_hint}",
                parse_mode="Markdown",
            )

        elif callback_data == "presentasi_accept":
            if not query or not context.user_data:
                return
            draft = context.user_data.get("presentasi_draft", {})
            outline = draft.get("outline", "")
            if not outline:
                await query.edit_message_text("❌ Outline tidak ditemukan")
                return

            topik = draft.get("topik", "Presentasi")
            await query.edit_message_text(
                f"✅ *Outline Presentasi Diterima*\n\n"
                f"📊 Topik: _{topik}_\n\n"
                f"Anda bisa:\n"
                f"• Copy outline ini ke PowerPoint\n"
                f"• Gunakan /sek untuk membuat presentasi baru",
                parse_mode="Markdown",
            )
            context.user_data.pop("presentasi_draft", None)
            context.user_data.pop("presentasi_state", None)

        elif callback_data == "presentasi_retry":
            if not query or not context.user_data:
                return
            context.user_data["presentasi_state"] = "presentasi_topik"
            await query.edit_message_text(
                "📊 *Buat Ulang Presentasi*\n\n"
                "Deskripsikan presentasi yang ingin dibuat (dengan detail lebih lengkap jika perlu):",
                parse_mode="Markdown",
            )

        elif callback_data == "presentasi_cancel":
            if not query or not context.user_data:
                return
            context.user_data.pop("presentasi_draft", None)
            context.user_data.pop("presentasi_state", None)
            await query.edit_message_text("❌ Pembuatan presentasi dibatalkan.")

        # ── Smart Surat Generator (dari Quick Export) ──────────────────────────
        elif callback_data.startswith("surat_tpl_"):
            if not query or not context.user_data or not update.effective_user:
                return

            user_id = update.effective_user.id
            template_type = callback_data.split("_")[2]  # proposal, offering, request, all
            source_result = context.user_data.get("surat_source_result", "")
            source_title = context.user_data.get("surat_source_title", "Hasil Riset")

            if not source_result:
                await query.edit_message_text("❌ Hasil sumber tidak ditemukan.")
                return

            context.user_data["surat_template_type"] = template_type
            context.user_data["surat_gen_state"] = "generating"

            await query.edit_message_text(
                f"🎯 *Generate Surat Template:* {template_type.upper()}\n\n"
                "⏳ Claude sedang membuat surat dengan Hermes Agent + Claude Skills...",
                parse_mode="Markdown",
            )

            try:
                async def on_progress_surat(text: str):
                    try:
                        await query.edit_message_text(text, parse_mode="Markdown")
                    except Exception:
                        pass

                surat_content = await self._generate_surat_with_hermes(
                    source_result=source_result,
                    source_title=source_title,
                    template_type=template_type,
                    user_id=user_id,
                    on_progress=on_progress_surat
                )

                context.user_data["surat_generated"] = {
                    "template": template_type,
                    "content": surat_content,
                    "source": source_title,
                    "timestamp": _dt.now().isoformat(),
                }

                # Display surat preview dengan opsi download/edit
                keyboard = [
                    [InlineKeyboardButton("📥 Download PDF", callback_data="surat_dl_pdf"),
                     InlineKeyboardButton("📝 Edit", callback_data="surat_edit")],
                    [InlineKeyboardButton("💾 Kirim Email", callback_data="surat_send_email"),
                     InlineKeyboardButton("❌ Batal", callback_data="surat_cancel")],
                ]

                preview = (surat_content[:2000] + "\n\n...[terpotong]") if len(surat_content) > 2000 else surat_content
                await query.edit_message_text(
                    f"✅ *Surat Generate:* {template_type.upper()}\n\n"
                    f"📋 *Sumber:* _{source_title}_\n\n"
                    f"```\n{preview}\n```",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown",
                )
            except Exception as e:
                logger.exception("Surat generation error: %s", e)
                await query.edit_message_text(f"❌ Gagal generate surat: {e}", parse_mode="Markdown")

        elif callback_data.startswith("surat_"):
            if callback_data == "surat_dl_pdf":
                surat_gen = context.user_data.get("surat_generated", {})
                if not surat_gen:
                    await query.edit_message_text("❌ Data surat tidak ditemukan.")
                    return

                await query.edit_message_text("📄 Membuat PDF dengan letterhead ATG...", parse_mode="Markdown")
                try:
                    perihal = surat_gen.get("template", "Surat").upper()
                    pdf_path = self.surat_gen.generate_pdf(
                        perihal=perihal,
                        isi=surat_gen.get("content", ""),
                    )

                    if query.message and query.message.chat:
                        with open(pdf_path, "rb") as f:
                            await query.message.chat.send_document(
                                document=f,
                                filename=f"surat_{surat_gen.get('template')}.pdf",
                                caption=f"📄 Surat {perihal} — PT. Arunika",
                            )
                    await query.delete_message()
                except Exception as e:
                    logger.exception("PDF generation error: %s", e)
                    await query.edit_message_text(f"❌ Gagal membuat PDF: {e}", parse_mode="Markdown")

            elif callback_data == "surat_edit":
                context.user_data["surat_gen_state"] = "editing"
                await query.edit_message_text(
                    "✏️ *Edit Surat*\n\n"
                    "Masukkan perubahan atau penambahan untuk surat:\n"
                    "(Contoh: Ubah nama PT, tambah CC, dll)",
                    parse_mode="Markdown",
                )

            elif callback_data == "surat_send_email":
                surat_gen = context.user_data.get("surat_generated", {})
                if not surat_gen:
                    await query.edit_message_text("❌ Data surat tidak ditemukan.")
                    return

                context.user_data["surat_email_state"] = "email_to"
                await query.edit_message_text(
                    "📧 *Kirim Surat via Email*\n\n"
                    "Masukkan alamat email penerima surat:\n"
                    "_(Contoh: nama@perusahaan.com)_",
                    parse_mode="Markdown",
                )

            elif callback_data == "surat_cancel":
                context.user_data.pop("surat_source_result", None)
                context.user_data.pop("surat_source_title", None)
                context.user_data.pop("surat_template_type", None)
                context.user_data.pop("surat_generated", None)
                context.user_data.pop("surat_gen_state", None)
                await query.edit_message_text("❌ Pembuatan surat dibatalkan.")

        elif callback_data.startswith("sek_"):
            feature = callback_data.split("_")[1]
            await query.edit_message_text(f"⏳ Fitur sekretaris: {feature} akan segera diimplementasikan!")

        elif callback_data.startswith("sosmed_"):
            feature = callback_data.split("_")[1]
            await query.edit_message_text(f"⏳ Fitur Social Media: {feature} akan segera diimplementasikan!")

        elif callback_data.startswith("res_"):
            feature = callback_data.split("_")[1]
            await query.edit_message_text(f"⏳ Fitur Resources: {feature} akan segera diimplementasikan!")

        elif callback_data.startswith("auto_"):
            feature = callback_data.split("_")[1]
            await query.edit_message_text(f"⏳ Fitur Automation: {feature} akan segera diimplementasikan!")

        # ── Export hasil ke format lain ──────────────────────────────────
        elif callback_data.startswith("export_"):
            if not query or not context.user_data:
                return
            last_result = context.user_data.get("last_result", {})
            if not last_result:
                await query.edit_message_text("❌ Tidak ada hasil untuk dikonversi.")
                return

            export_type = callback_data.split("_")[1]  # surat, pdf, excel, presentasi, sosmed
            result_text = last_result.get("text", "")
            result_title = last_result.get("title", "Hasil")

            if export_type == "surat":
                if context.user_data is not None:
                    context.user_data["surat_source_result"] = result_text
                    context.user_data["surat_source_title"] = result_title

                keyboard = [
                    [InlineKeyboardButton("📋 Proposal Kerjasama", callback_data="surat_tpl_proposal")],
                    [InlineKeyboardButton("🎁 Penawaran Produk", callback_data="surat_tpl_offering")],
                    [InlineKeyboardButton("📞 Permohonan/Undangan", callback_data="surat_tpl_request")],
                    [InlineKeyboardButton("🎯 Generate Semua Template", callback_data="surat_tpl_all")],
                ]
                await query.edit_message_text(
                    "📄 *Jadikan Surat Resmi ATG*\n\n"
                    "Pilih template surat yang akan dihasilkan dari riset/analisis ini:\n"
                    f"📊 *Source:* _{result_title}_\n\n"
                    "Claude akan generate surat profesional dengan Claude Skills...",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown",
                )

            elif export_type == "pdf":
                await query.edit_message_text("⏳ Membuat PDF...")
                try:
                    pdf_path = await generate_document_pdf_async(
                        title=result_title,
                        content=result_text,
                        author="Reflective Koala Agent"
                    )
                    with open(pdf_path, "rb") as f:
                        if query.message and query.message.chat:
                            await query.message.chat.send_document(
                                document=f,
                                filename=f"{result_title[:40]}.pdf",
                                caption=f"📄 {result_title}",
                            )
                    await query.delete_message()
                except Exception as e:
                    logger.exception("PDF export error: %s", e)
                    await query.edit_message_text(f"❌ Gagal membuat PDF: {e}")

            elif export_type == "excel":
                await query.edit_message_text(
                    "⏳ Membuat Excel...\n\n"
                    "_Fitur Excel sedang dalam pengembangan._\n"
                    "Untuk sekarang, gunakan format PDF atau copy teks langsung ke Excel.",
                    parse_mode="Markdown",
                )

            elif export_type == "presentasi":
                if context.user_data is not None:
                    context.user_data["presentasi_state"] = "presentasi_topic_from_result"
                    context.user_data["presentasi_draft"] = {
                        "source_result": result_text,
                        "source_title": result_title,
                    }
                await query.edit_message_text(
                    "🎨 *Jadikan Presentasi*\n\n"
                    "Claude akan membuat outline presentasi dari hasil riset ini.\n"
                    "Apakah ingin menyesuaikan fokus presentasi?\n\n"
                    "_Enter untuk gunakan topik otomatis, atau tulis penyesuaian._",
                    parse_mode="Markdown",
                )
                if context.user_data is not None:
                    context.user_data["presentasi_state"] = "presentasi_topik"

            elif export_type == "sosmed":
                await query.edit_message_text(
                    "📱 *Jadikan Konten Sosial Media + Gambar*\n\n"
                    "Pilih platform:\n\n"
                    "[Instagram] [TikTok] [LinkedIn] [Twitter]",
                    parse_mode="Markdown",
                )

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        # Log exception agar bisa dilacak kenapa pesan tidak memunculkan reply.
        logger.exception("Telegram handler error: update=%s exc=%s", update, context.error)

    # ──────────────────────────────────────────────────────────────────────
    # ATTACHMENT HANDLER (dokumen & foto)
    # ──────────────────────────────────────────────────────────────────────

    async def _process_attachment(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        file_id: str,
        file_name: str,
        caption: str,
        file_size: int,
    ):
        """Unduh file, ekstrak teks, kirim ke AI dengan caption sebagai instruksi."""
        msg = update.message
        if not msg:
            return
        user_id = update.effective_user.id if update.effective_user else 0

        # Cek ukuran (max 20 MB)
        if file_size and file_size > 20 * 1024 * 1024:
            await msg.reply_text("❌ File terlalu besar (max 20 MB)")
            return

        status = await msg.reply_text(f"📎 Membaca *{file_name}*...", parse_mode="Markdown")

        # Unduh ke folder temp
        from pathlib import Path as _Path
        tmp_dir = _Path(settings.output_dir) / "temp"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        tmp_path = tmp_dir / file_name

        try:
            tg_file = await context.bot.get_file(file_id)
            await tg_file.download_to_drive(str(tmp_path))
        except Exception as e:
            await status.edit_text(f"❌ Gagal mengunduh file: {e}")
            return

        # Ekstrak teks
        result = await extract_text(str(tmp_path), file_name)

        # Hapus file temp
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass

        if "error" in result:
            await status.edit_text(f"❌ {result['error']}", parse_mode="Markdown")
            return

        extracted = result["text"]
        pages     = result.get("pages", 1)
        ftype     = result.get("file_type", "file").upper()
        chars     = len(extracted)

        # ── Cek apakah caption adalah perintah /memori ─────────────────────────
        caption_clean = caption.strip().lower()
        save_to_memory = caption_clean in ("/memori", "memori", "/memory", "memory")

        # ── Cek apakah ini dokumen Arunika ─────────────────────────────────────
        is_arunika_doc = any(
            keyword in file_name.lower() or keyword in extracted[:2000].lower()
            for keyword in ["arunika", "pt. arunika", "arunika teknologi"]
        )

        # ── PATH 1: Caption /memori → SIMPAN ke archival memory ───────────────
        if save_to_memory or is_arunika_doc:
            await status.edit_text(
                f"📎 *{file_name}* dibaca ({pages} hal · {chars:,} kar)\n\n"
                f"{self._render_progress_bar(1, 3, 'Extracting info')}\n\n"
                f"{'🏢 Dokumen Arunika terdeteksi!' if is_arunika_doc else '🧠 Mode simpan memori aktif'}\n"
                "Mengekstrak & menyimpan ke memori...",
                parse_mode="Markdown",
            )

            router = await self._ensure_model_router(user_id)

            # Step 1: Extract structured summary
            extract_prompt = f"""Buat ringkasan terstruktur dari dokumen ini untuk disimpan ke memori AI.

Format output:
JUDUL_DOKUMEN: [nama/jenis dokumen]
TANGGAL: [tanggal dokumen jika ada]
RINGKASAN: [ringkasan 2-3 kalimat]
INFORMASI_PENTING:
- [poin penting 1]
- [poin penting 2]
- [dst]
{'''
UNTUK DOKUMEN ARUNIKA - EKSTRAK JUGA:
NAMA_PERUSAHAAN: [PT. Arunika Teknologi Global]
ALAMAT: [alamat lengkap]
DIREKTUR: [nama direktur]
TELEPON: [nomor telepon]
EMAIL: [email resmi]
WEBSITE: [website]
NPWP: [nomor NPWP jika ada]
AKTA_NOTARIS: [nomor akta, notaris, tanggal]
''' if is_arunika_doc else ''}
--- DOKUMEN ({file_name}) ---
{extracted[:5000]}"""

            try:
                summary, _ = await router.call(
                    messages=[{"role": "user", "content": extract_prompt}],
                    temperature=0.2,
                    max_tokens=2000,
                )

                await status.edit_text(
                    f"📎 *{file_name}*\n\n"
                    f"{self._render_progress_bar(2, 3, 'Saving to memory')}\n\n"
                    "💾 Menyimpan ke Archival Memory...",
                    parse_mode="Markdown",
                )

                mem = self.agent.get_memory(user_id)

                # Simpan ringkasan ke archival memory (bisa dicari nanti)
                tags = ["dokumen", file_name.split(".")[0].lower()]
                if is_arunika_doc:
                    tags += ["arunika", "perusahaan", "company-info"]
                await mem.archival_memory_insert(
                    content=f"[{file_name}]\n{summary}",
                    tags=tags,
                )

                # Untuk dokumen Arunika → update juga core_memory (human block)
                # agar selalu tersedia di setiap percakapan
                if is_arunika_doc:
                    core_update = (
                        f"\n\n=== DATA PT. ARUNIKA TEKNOLOGI GLOBAL ===\n"
                        f"Sumber: {file_name}\n"
                        f"{summary}"
                    )
                    # Coba hapus entry Arunika lama dulu (replace)
                    await mem.ensure_loaded()
                    if "PT. ARUNIKA" in mem._human or "Arunika" in mem._human:
                        # Update existing
                        old_marker = "=== DATA PT. ARUNIKA"
                        if old_marker in mem._human:
                            idx = mem._human.index(old_marker)
                            old_section = mem._human[idx:]
                            await mem.core_memory_replace("human", old_section, core_update)
                        else:
                            await mem.core_memory_append("human", core_update)
                    else:
                        await mem.core_memory_append("human", core_update)

                await status.edit_text(
                    f"✅ *Tersimpan ke Memori AI!*\n\n"
                    f"{self._render_progress_bar(3, 3, 'Complete ✅')}\n\n"
                    f"📎 *File:* {file_name}\n"
                    f"📄 {pages} halaman · {chars:,} karakter\n"
                    + ("🏢 Data Arunika → Core Memory (selalu aktif)\n" if is_arunika_doc else "")
                    + "📚 → Archival Memory (bisa dicari dengan /recall)\n\n"
                    + f"_Gunakan `/recall` untuk mencari nanti_",
                    parse_mode="Markdown",
                )
                return

            except Exception as e:
                logger.exception("Memory save error: %s", e)
                await status.edit_text(
                    f"⚠️ Gagal simpan ke memori: {e}\n\nMelanjutkan analisis biasa...",
                    parse_mode="Markdown",
                )

        # ── PATH 2: Normal processing ──────────────────────────────────────────
        await status.edit_text(
            f"✅ *{file_name}* berhasil dibaca\n"
            f"📄 {ftype} · {pages} halaman · {chars:,} karakter\n\n"
            f"⏳ AI sedang memproses...",
            parse_mode="Markdown",
        )

        # Bangun prompt: gabungkan instruksi caption + isi file
        user_instruction = caption.strip() if caption and not save_to_memory else "Analisis dan ringkas isi dokumen ini."
        ai_prompt = (
            f"{user_instruction}\n\n"
            f"--- ISI DOKUMEN ({file_name}) ---\n"
            f"{extracted}"
        )

        # Kirim ke AI dengan model user
        await msg.chat.send_action("typing")
        try:
            router = await self._ensure_model_router(user_id)
            response, _ = await router.call(
                messages=[{"role": "user", "content": ai_prompt}],
                temperature=0.5,
                max_tokens=4096,
            )
            await status.edit_text(
                f"📎 *{file_name}* — selesai dianalisis\n"
                f"{self._render_progress_bar(2, 2, 'Complete ✅')}",
                parse_mode="Markdown"
            )
            await self._send_long(update, response)
        except Exception as e:
            logger.exception("Attachment AI error: %s", e)
            await status.edit_text(f"❌ Gagal memproses dokumen: {e}")

    async def document_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler untuk file dokumen (PDF, DOCX, TXT, dll) dan gambar (PNG, JPG)."""
        user_id = update.effective_user.id if update.effective_user else 0
        if not await check_user_allowed(user_id):
            return
        msg = update.message
        if not msg or not msg.document:
            return

        doc     = msg.document
        caption = msg.caption or ""
        fname   = doc.file_name or "file"

        # Gambar dikirim sebagai dokumen (bukan foto) → gunakan vision
        if is_image(fname):
            mime = doc.mime_type or "image/jpeg"
            await self._process_image_vision(
                update, context,
                file_id=doc.file_id,
                media_type=mime,
                caption=caption,
            )
            return

        if not is_supported(fname):
            from src.tools.file_reader import FORMAT_LABEL
            await msg.reply_text(
                f"⚠️ Format *{fname.split('.')[-1].upper()}* belum didukung untuk ekstraksi teks.\n\n"
                f"Format yang bisa dibaca:\n{FORMAT_LABEL}",
                parse_mode="Markdown",
            )
            return

        await self._process_attachment(
            update, context,
            file_id=doc.file_id,
            file_name=fname,
            caption=caption,
            file_size=doc.file_size or 0,
        )

    async def _process_image_vision(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        file_id: str,
        media_type: str,
        caption: str,
    ):
        """Unduh gambar, encode base64, kirim ke AI via vision."""
        msg = update.message
        if not msg:
            return
        user_id = update.effective_user.id if update.effective_user else 0

        status = await msg.reply_text("🔍 Menganalisis gambar dengan AI...")
        try:
            tg_file = await context.bot.get_file(file_id)
            photo_bytes = bytes(await tg_file.download_as_bytearray())
            import base64
            b64_data = base64.b64encode(photo_bytes).decode()

            user_instruction = caption.strip() if caption else "Deskripsikan dan analisis gambar ini secara detail."
            vision_message = {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": b64_data,
                        },
                    },
                    {"type": "text", "text": user_instruction},
                ],
            }

            router = await self._ensure_model_router(user_id)
            response, _ = await router.call(
                messages=[vision_message],
                temperature=0.5,
                max_tokens=4096,
            )
            await status.edit_text(
                f"📸 Gambar selesai dianalisis\n"
                f"{self._render_progress_bar(2, 2, 'Complete ✅')}",
                parse_mode="Markdown"
            )
            await self._send_long(update, response)
        except Exception as e:
            logger.exception("Image vision error: %s", e)
            await status.edit_text(f"❌ Gagal menganalisis gambar: {e}")

    async def photo_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler untuk foto — analisis dengan AI vision."""
        user_id = update.effective_user.id if update.effective_user else 0
        if not await check_user_allowed(user_id):
            return
        msg = update.message
        if not msg or not msg.photo:
            return

        # Telegram selalu kompres foto menjadi JPEG
        photo = msg.photo[-1]
        await self._process_image_vision(
            update, context,
            file_id=photo.file_id,
            media_type="image/jpeg",
            caption=msg.caption or "",
        )

    async def debug_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Fallback untuk mendeteksi command yang tidak ter-match ke handler spesifik.
        msg = update.message
        if not msg or not msg.text:
            return
        text = msg.text.strip()
        user_id = update.effective_user.id if update.effective_user else None
        print(f"[TG_DEBUG] debug_command called user_id={user_id} text={text!r}", flush=True)
        logger.info("Telegram debug_command received user_id=%s text=%r", user_id, text)

        # Reply supaya kita tahu command memang masuk ke fallback ini.
        try:
            await msg.reply_text(f"🧪 DEBUG: command diterima di fallback: {text}")
        except Exception:
            # jangan sampai fallback error mengganggu handler lain
            pass

    def setup_handlers(self, app: Application):
        app.add_error_handler(self.error_handler)

        app.add_handler(CommandHandler("start", self.start))
        app.add_handler(CommandHandler("help", self.help_cmd))
        app.add_handler(CommandHandler("settings", self.settings))
        app.add_handler(CommandHandler("credit", self.credit))
        app.add_handler(CommandHandler("usage", self.credit))
        app.add_handler(CommandHandler("model", self.model_cmd))
        app.add_handler(CommandHandler("compress", self.compress))
        app.add_handler(CommandHandler("padatkan", self.compress))
        app.add_handler(CommandHandler("fungsi", self.fungsi))
        app.add_handler(CommandHandler("menu", self.fungsi))
        app.add_handler(CommandHandler("sek", self.sekretaris))
        app.add_handler(CommandHandler("sekretaris", self.sekretaris))
        app.add_handler(CommandHandler("rnd", self.rnd))
        app.add_handler(CommandHandler("sosmed", self.sosmed))
        app.add_handler(CommandHandler("resources", self.resources))
        app.add_handler(CommandHandler("rag", self.resources))
        app.add_handler(CommandHandler("auto", self.automation))
        app.add_handler(CommandHandler("gambar", self.gambar))
        app.add_handler(CommandHandler("image", self.gambar))
        app.add_handler(CommandHandler("email", self.email_cmd))
        app.add_handler(CommandHandler("kirim", self.email_cmd))
        app.add_handler(CommandHandler("code", self.code_cmd))
        app.add_handler(CommandHandler("python", self.code_cmd))
        app.add_handler(CommandHandler("run", self.code_cmd))
        app.add_handler(CommandHandler("perbaiki", self.perbaiki_cmd))
        app.add_handler(CommandHandler("improve", self.perbaiki_cmd))
        app.add_handler(CommandHandler("karir", self.karir))
        app.add_handler(CommandHandler("career", self.karir))
        app.add_handler(CommandHandler("kerja", self.karir))
        app.add_handler(CommandHandler("agen", self.agen_cmd))
        app.add_handler(CommandHandler("agent", self.agen_cmd))
        app.add_handler(CommandHandler("h", self.hermes_cmd))
        app.add_handler(CommandHandler("hermes", self.hermes_cmd))
        app.add_handler(CommandHandler("recall", self.recall_cmd))
        app.add_handler(CommandHandler("ingat", self.recall_cmd))
        app.add_handler(CommandHandler("pdf", self.pdf_cmd))
        app.add_handler(CommandHandler("tools", self.tools_cmd))
        app.add_handler(CommandHandler("skill", self.tools_cmd))
        app.add_handler(CommandHandler("memori", self.memori_cmd))
        app.add_handler(CommandHandler("memory", self.memori_cmd))
        app.add_handler(CommandHandler("agen24", self.agen24_cmd))
        app.add_handler(CommandHandler("jadwal", self.agen24_cmd))

        app.add_handler(CallbackQueryHandler(self.provider_callback, pattern="^provider_"))
        app.add_handler(CallbackQueryHandler(self.orgroup_callback, pattern="^orgroup_"))
        app.add_handler(CallbackQueryHandler(self.setmodel_callback, pattern="^setmodel_"))
        app.add_handler(CallbackQueryHandler(self.model_callback, pattern="^model_"))
        app.add_handler(CallbackQueryHandler(self.img_model_callback, pattern="^img_"))
        app.add_handler(CallbackQueryHandler(self.email_callback, pattern="^email_"))
        app.add_handler(CallbackQueryHandler(self.karir_callback, pattern="^karir_"))
        # surat_callback hanya untuk aksi akhir (download/email/batal)
        app.add_handler(CallbackQueryHandler(self.improve_callback, pattern="^improve_"))
        app.add_handler(CallbackQueryHandler(self.surat_callback, pattern="^surat_(download|email|batal)$"))
        # module_callback: sek_, rnd_, surat_mode_, export_, presentasi_, dll
        app.add_handler(CallbackQueryHandler(self.module_callback, pattern="^(sek_|rnd_|sosmed_|res_|auto_|surat_mode_|export_|presentasi_)"))

        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.text_message))
        app.add_handler(MessageHandler(filters.Document.ALL, self.document_handler))
        app.add_handler(MessageHandler(filters.PHOTO, self.photo_handler))
        app.add_handler(MessageHandler(filters.COMMAND, self.debug_command))
