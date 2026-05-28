from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from src.auth import check_user_allowed
from src.agent import ATGAgent, ANTHROPIC_MODELS, OPENROUTER_MODELS, fetch_anthropic_models, fetch_lmstudio_models
from src.agent.model_router import OPENROUTER_IMAGE_MODELS, generate_image_openrouter
from src.database import set_user_model, get_user_model, get_user_usage, get_usage_by_model
from src.config import settings
from src.modules.rnd import RndHandler
from src.tools.email_sender import send_email, test_smtp_connection
from src.tools.surat_generator import SuratGenerator
from src.tools.code_executor import execute_python, apply_improvement, restart_bot
from src.tools.api_balance import check_openrouter_balance, check_anthropic_balance, IDR_RATE
import aiosqlite
import logging
from datetime import datetime as _dt

logger = logging.getLogger(__name__)

class TelegramGateway:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.agent = ATGAgent()
        self.rnd_module = RndHandler()
        self.surat_gen = SuratGenerator(settings.output_dir)

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

        # ── Code REPL state ────────────────────────────────────────────────
        if (context.user_data or {}).get("code_state") == "waiting":
            if context.user_data is not None:
                context.user_data.pop("code_state", None)
            if update.message:
                await self._run_and_reply(update.message, user_message)
            return

        # ── Surat state machine ────────────────────────────────────────────
        surat_state = (context.user_data or {}).get("surat_state")
        if surat_state:
            await self._handle_surat_state(update, context, surat_state, user_message)
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
            # AI draft: generate full surat from brief
            ud["surat_state"] = None
            user_id = update.effective_user.id if update.effective_user else 0
            await msg.chat.send_action("typing")
            status = await msg.reply_text(
                "🤖 AI sedang menyusun surat...\n⏱ Estimasi 15-20 detik"
            )
            router = await self._ensure_model_router(user_id)

            ai_prompt = (
                "Kamu adalah Corporate Secretary PT. Arunika Teknologi Global. "
                "Buat surat resmi profesional dengan gaya Islami berdasarkan brief berikut.\n\n"
                f"Brief: {user_message}\n\n"
                "Balas HANYA dalam format ini (tanpa tambahan apapun):\n"
                "TUJUAN_NAMA: <nama lengkap penerima>\n"
                "TUJUAN_JABATAN: <jabatan penerima>\n"
                "TUJUAN_INSTITUSI: <nama institusi/perusahaan>\n"
                "TUJUAN_KOTA: <kota, default: Tempat>\n"
                "PERIHAL: <perihal surat singkat>\n"
                "LAMPIRAN: <- atau jumlah lampiran>\n"
                "PENANDATANGAN_NAMA: <nama penandatangan, default: Ir. Rachmat Ari Kusumanto>\n"
                "PENANDATANGAN_JABATAN: <jabatan penandatangan, default: Direktur>\n"
                "ISI:\n"
                "<isi surat profesional Islami, minimal 3 paragraf. "
                "Jangan sertakan salam pembuka/penutup, bismillah, letterhead, atau tanda tangan — "
                "itu sudah ada di template. Tulis hanya isi/body paragraf surat.>"
            )
            try:
                response, _ = await router.call(
                    messages=[{"role": "user", "content": ai_prompt}],
                    temperature=0.4,
                    max_tokens=2000,
                )
                fields: dict[str, str] = {}
                isi_lines: list[str] = []
                in_isi = False
                for line in response.strip().splitlines():
                    ul = line.upper()
                    if ul.startswith("ISI:"):
                        in_isi = True
                        rest = line.split(":", 1)[1].strip()
                        if rest:
                            isi_lines.append(rest)
                        continue
                    if in_isi:
                        isi_lines.append(line)
                        continue
                    for key in ["TUJUAN_NAMA", "TUJUAN_JABATAN", "TUJUAN_INSTITUSI",
                                "TUJUAN_KOTA", "PERIHAL", "LAMPIRAN",
                                "PENANDATANGAN_NAMA", "PENANDATANGAN_JABATAN"]:
                        if ul.startswith(key + ":"):
                            fields[key] = line.split(":", 1)[1].strip()

                draft.update({
                    "tujuan_nama":          fields.get("TUJUAN_NAMA", ""),
                    "tujuan_jabatan":       fields.get("TUJUAN_JABATAN", ""),
                    "tujuan_institusi":     fields.get("TUJUAN_INSTITUSI", ""),
                    "tujuan_kota":          fields.get("TUJUAN_KOTA", "Tempat"),
                    "perihal":              fields.get("PERIHAL", ""),
                    "lampiran":             fields.get("LAMPIRAN", "-"),
                    "penandatangan_nama":   fields.get("PENANDATANGAN_NAMA", "Ir. Rachmat Ari Kusumanto"),
                    "penandatangan_jabatan":fields.get("PENANDATANGAN_JABATAN", "Direktur"),
                    "isi":                  "\n\n".join(isi_lines).strip(),
                })
                await status.delete()
                await self._show_surat_preview(update, context, draft)
            except Exception as e:
                logger.exception("Surat AI draft error: %s", e)
                await status.edit_text(f"❌ Gagal menyusun surat: {e}")

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
                await query.edit_message_text("❌ Draft surat tidak lengkap. Mulai ulang /sek")
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
                                f"Gunakan /sek jika ingin kirim via email.",
                            ),
                            parse_mode="Markdown",
                        )
            except Exception as e:
                logger.exception("Surat PDF error: %s", e)
                await query.edit_message_text(f"❌ Gagal membuat PDF:\n{e}")

        elif data == "surat_email":
            if not draft.get("perihal") or not draft.get("isi"):
                await query.edit_message_text("❌ Draft tidak lengkap.")
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
        app.add_handler(CommandHandler("code", self.code_cmd))
        app.add_handler(CommandHandler("python", self.code_cmd))
        app.add_handler(CommandHandler("run", self.code_cmd))
        app.add_handler(CommandHandler("perbaiki", self.perbaiki_cmd))
        app.add_handler(CommandHandler("improve", self.perbaiki_cmd))

        app.add_handler(CallbackQueryHandler(self.provider_callback, pattern="^provider_"))
        app.add_handler(CallbackQueryHandler(self.setmodel_callback, pattern="^setmodel_"))
        app.add_handler(CallbackQueryHandler(self.model_callback, pattern="^model_"))
        app.add_handler(CallbackQueryHandler(self.img_model_callback, pattern="^img_"))
        app.add_handler(CallbackQueryHandler(self.email_callback, pattern="^email_"))
        # surat_callback hanya untuk aksi akhir (download/email/batal)
        app.add_handler(CallbackQueryHandler(self.improve_callback, pattern="^improve_"))
        app.add_handler(CallbackQueryHandler(self.surat_callback, pattern="^surat_(download|email|batal)$"))
        # module_callback: sek_, rnd_, surat_mode_ (mode pilihan surat), dll
        app.add_handler(CallbackQueryHandler(self.module_callback, pattern="^(sek_|rnd_|sosmed_|res_|auto_|surat_mode_)"))

        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.text_message))
        # Jika ada command yang tidak ter-match handler spesifik, akan ketahuan lewat log di debug_command.
        app.add_handler(MessageHandler(filters.COMMAND, self.debug_command))
