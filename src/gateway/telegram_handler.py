from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from src.auth import check_user_allowed
from src.agent import ATGAgent, ANTHROPIC_MODELS, OPENROUTER_MODELS, fetch_anthropic_models, fetch_lmstudio_models
from src.agent.model_router import OPENROUTER_IMAGE_MODELS, generate_image_openrouter
from src.database import set_user_model, get_user_model, get_user_usage, get_usage_by_model
from src.config import settings
from src.modules.rnd import RndHandler
from src.tools.email_sender import send_email, test_smtp_connection
import aiosqlite
import logging

logger = logging.getLogger(__name__)

class TelegramGateway:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.agent = ATGAgent()
        self.rnd_module = RndHandler()

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

AI Agent komprehensif untuk PT. Arunika Teknologi Global.

Pilih fungsi:
• /sek - Sekretaris (surat, presentasi, notulensi)
• /rnd - R&D (riset mitra, analisis)
• /sosmed - Social Media (konten, analitik)
• /resources - Resources (knowledge base, RAG)
• /auto - Automation (python, cron)
• /fungsi - Lihat semua fungsi yang tersedia
• /model - Pilih model Claude dari API key Anda
• /settings - Pengaturan provider & model
• /compress - Padatkan percakapan (hemat token)
• /credit - Cek penggunaan & estimasi biaya API
• /help - Bantuan

Atau ketik pertanyaan bebas! 🤖"""

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
        elif provider == "anthropic":
            models = ANTHROPIC_MODELS
            keyboard = [
                [InlineKeyboardButton(display, callback_data=f"model_{model}")]
                for model, display in models.items()
            ]
        else:
            models = OPENROUTER_MODELS
            keyboard = [
                [InlineKeyboardButton(display, callback_data=f"model_{model}")]
                for model, display in models.items()
            ]

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(f"Pilih model {provider}:", reply_markup=reply_markup)

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

    async def _send_long(self, update: Update, text: str):
        """Send long text split into Telegram-safe chunks."""
        for i in range(0, len(text), 4096):
            await update.message.reply_text(text[i:i+4096])

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

            async def make_progress(msg_obj):
                async def on_progress(text: str):
                    try:
                        await msg_obj.edit_text(text, parse_mode="Markdown")
                    except Exception:
                        pass
                return on_progress

            if rnd_state == "riset":
                msg = await update.message.reply_text(
                    f"🔍 *Riset:* `{user_message}`\n\n"
                    "⏱ Estimasi: 20\\-30 detik\n"
                    "🌐 *Step 1/3* — Searching web via Firecrawl\\.\\.\\.",
                    parse_mode="MarkdownV2"
                )
                result = await self.rnd_module.riset_mitra(user_message, router, on_progress=await make_progress(msg))
                await msg.delete()
                await self._send_long(update, result)

            elif rnd_state == "swot":
                msg = await update.message.reply_text(
                    f"📈 *SWOT:* `{user_message}`\n\n"
                    "⏱ Estimasi: 20\\-30 detik\n"
                    "🌐 *Step 1/3* — Searching web via Firecrawl\\.\\.\\.",
                    parse_mode="MarkdownV2"
                )
                result = await self.rnd_module.analisis_swot(user_message, router, on_progress=await make_progress(msg))
                await msg.delete()
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
                    f"📋 *Proposal:* `{partner} × ATG`\n\n"
                    "⏱ Estimasi: 20\\-30 detik\n"
                    "🌐 *Step 1/3* — Searching profil mitra\\.\\.\\.",
                    parse_mode="MarkdownV2"
                )
                result = await self.rnd_module.buat_proposal(partner, user_message, router, on_progress=await make_progress(msg))
                await msg.delete()
                await self._send_long(update, result)

            elif rnd_state == "tech":
                msg = await update.message.reply_text(
                    f"🔬 *Riset Teknologi:* `{user_message}`\n\n"
                    "⏱ Estimasi: 20\\-30 detik\n"
                    "🌐 *Step 1/3* — Searching latest tech news\\.\\.\\.",
                    parse_mode="MarkdownV2"
                )
                result = await self.rnd_module.riset_teknologi(user_message, router, on_progress=await make_progress(msg))
                await msg.delete()
                await self._send_long(update, result)

            elif rnd_state == "scrape":
                url = user_message if user_message.startswith("http") else "https://" + user_message
                msg = await update.message.reply_text(
                    f"🕷️ *Scraping:* `{url}`\n\n"
                    "⏱ Estimasi: 15\\-20 detik\n"
                    "🌐 Mengambil konten website\\.\\.\\.",
                    parse_mode="MarkdownV2"
                )
                result = await self.rnd_module.scrape_website(url, router, on_progress=await make_progress(msg))
                await msg.delete()
                await self._send_long(update, result)

            context.user_data.pop("rnd_state", None)
            context.user_data.pop("rnd_partner", None)
            return

        # ── Email state machine ────────────────────────────────────────────
        email_state = (context.user_data or {}).get("email_state")
        if email_state:
            await self._handle_email_state(update, context, email_state, user_message)
            return

        # ── Normal chat ────────────────────────────────────────────────────
        await update.message.chat.send_action("typing")
        try:
            response = await self.agent.chat(user_id, user_message)
            await self._send_long(update, response)
        except Exception as e:
            logger.error(f"Error: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")

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
                "⏱ Estimasi: 20\\-30 detik\n"
                "🌐 *Step 1/3* — Searching web via Firecrawl\\.\\.\\.",
                parse_mode="MarkdownV2"
            )
            async def on_progress(text):
                try:
                    await msg.edit_text(text, parse_mode="Markdown")
                except Exception:
                    pass
            result = await self.rnd_module.riset_mitra(args, router, on_progress=on_progress)
            await msg.delete()
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

        async with aiosqlite.connect(self.db_path) as db:
            summary = await get_user_usage(db, user_id)
            by_model = await get_usage_by_model(db, user_id)
            provider, model_name = await get_user_model(db, user_id)

        total_tokens = summary["total_input"] + summary["total_output"]
        cost_idr = summary["total_cost"] * 16000  # approximate USD→IDR

        lines = [
            "💳 *Penggunaan API Anda*",
            "",
            f"🔢 Total request: *{summary['total_calls']}x*",
            f"📥 Token input: *{summary['total_input']:,}*",
            f"📤 Token output: *{summary['total_output']:,}*",
            f"📊 Total token: *{total_tokens:,}*",
            f"💰 Estimasi biaya: *${summary['total_cost']:.6f}* (~Rp {cost_idr:,.0f})",
            "",
        ]

        if by_model:
            lines.append("📋 *Per Model:*")
            for row in by_model:
                prov, mdl, inp, out, cost, calls = row
                mdl_short = mdl.split("/")[-1] if "/" in mdl else mdl
                lines.append(f"  • `{mdl_short}` — {calls}x, ${cost:.6f}")
            lines.append("")

        lines += [
            f"⚙️ Model aktif: *{model_name}*",
            f"🔌 Provider: *{provider}*",
            "",
            "ℹ️ _Biaya di atas adalah estimasi berdasarkan token yang digunakan._",
            "_Cek tagihan resmi di console.anthropic.com_",
        ]

        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    async def fungsi(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not await check_user_allowed(user_id):
            return

        async with aiosqlite.connect(self.db_path) as db:
            provider, model_name = await get_user_model(db, user_id)

        model_short = model_name.split("/")[-1] if "/" in model_name else model_name

        text = (
            "📋 *DAFTAR FUNGSI REFLECTIVE KOALA*\n"
            f"_Model aktif: {model_short} ({provider})_\n"
            "─────────────────────────\n\n"

            "🤖 *AI & MODEL*\n"
            "  /model — Pilih model Claude dari API key\n"
            "  /settings — Pilih provider & model (Anthropic / OpenRouter)\n"
            "  /compress — Padatkan riwayat percakapan (hemat token)\n"
            "  /credit — Lihat estimasi penggunaan & biaya API\n\n"

            "📁 *MODUL UTAMA*\n"
            "  /sek — 📄 Sekretaris\n"
            "    ├ Buat surat dinas\n"
            "    ├ Buat presentasi\n"
            "    ├ Notulensi meeting\n"
            "    ├ Set agenda\n"
            "    └ Set reminder\n\n"
            "  /rnd — 🔬 Riset & Development\n"
            "    ├ 🔍 Riset calon mitra (web search + AI)\n"
            "    ├ 📈 Analisis SWOT (web search + AI)\n"
            "    ├ 📋 Buat proposal kemitraan\n"
            "    ├ 🔬 Riset teknologi terkini\n"
            "    └ 🕷️ Scrape & ringkas website\n\n"
            "  /sosmed — 📱 Social Media\n"
            "    ├ Buat konten IG/FB/TikTok/YouTube\n"
            "    ├ Analisis performa konten\n"
            "    └ Content calendar\n\n"
            "  /resources — 🗂 Knowledge Base\n"
            "    ├ Upload dokumen\n"
            "    ├ Semantic search (RAG)\n"
            "    └ Kelola produk & program ATG\n\n"
            "  /auto — ⚙️ Automation\n"
            "    ├ Jalankan Python script\n"
            "    ├ Set cron job\n"
            "    └ Web scraping\n\n"

            "🛠 *UTILITAS*\n"
            "  /fungsi — Tampilkan daftar ini\n"
            "  /start — Menu utama\n"
            "  /help — Panduan lengkap\n\n"

            "💬 *CHAT BEBAS*\n"
            "  Ketik pesan apapun → dijawab oleh AI\n"
            "  Konteks percakapan tersimpan otomatis\n"
        )

        await update.message.reply_text(text, parse_mode="Markdown")

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
            await msg.delete()
            await update.message.reply_photo(
                photo=image_url,
                caption=f"🎨 *Gambar selesai!*\n📝 _{prompt}_",
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
                await status.delete()
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

        # ── Other modules (placeholder) ───────────────────────────────────
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

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        # Log exception agar bisa dilacak kenapa pesan tidak memunculkan reply.
        logger.exception("Telegram handler error: update=%s exc=%s", update, context.error)

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

        app.add_handler(CallbackQueryHandler(self.provider_callback, pattern="^provider_"))
        app.add_handler(CallbackQueryHandler(self.setmodel_callback, pattern="^setmodel_"))
        app.add_handler(CallbackQueryHandler(self.model_callback, pattern="^model_"))
        app.add_handler(CallbackQueryHandler(self.img_model_callback, pattern="^img_"))
        app.add_handler(CallbackQueryHandler(self.email_callback, pattern="^email_"))
        app.add_handler(CallbackQueryHandler(self.module_callback, pattern="^(sek_|rnd_|sosmed_|res_|auto_)"))

        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.text_message))
        # Jika ada command yang tidak ter-match handler spesifik, akan ketahuan lewat log di debug_command.
        app.add_handler(MessageHandler(filters.COMMAND, self.debug_command))
