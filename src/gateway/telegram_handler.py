from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from src.auth import check_user_allowed
from src.agent import ATGAgent, ANTHROPIC_MODELS, OPENROUTER_MODELS
from src.database import set_user_model, get_user_model
import aiosqlite
import logging

logger = logging.getLogger(__name__)

class TelegramGateway:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.agent = ATGAgent()

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not await check_user_allowed(user_id):
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
• /settings - Pengaturan model AI
• /help - Bantuan

Atau ketik pertanyaan bebas! 🤖"""

        await update.message.reply_text(welcome_text)

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
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Pilih provider AI:", reply_markup=reply_markup)

    async def provider_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        user_id = query.from_user.id
        provider = query.data.split("_")[1]

        if provider == "anthropic":
            models = ANTHROPIC_MODELS
        else:
            models = OPENROUTER_MODELS

        keyboard = [
            [InlineKeyboardButton(display, callback_data=f"model_{model}")]
            for model, display in models.items()
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(f"Pilih model {provider}:", reply_markup=reply_markup)
        context.user_data["selected_provider"] = provider

    async def model_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        user_id = query.from_user.id
        model_name = query.data.split("_", 1)[1]
        provider = context.user_data.get("selected_provider", "anthropic")

        async with aiosqlite.connect(self.db_path) as db:
            await set_user_model(db, user_id, provider, model_name)

        await self.agent.init_model(provider, model_name)

        display = ANTHROPIC_MODELS.get(model_name) or OPENROUTER_MODELS.get(model_name, model_name)
        await query.edit_message_text(f"✅ Model diatur ke: {display}")

    async def text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not await check_user_allowed(user_id):
            await update.message.reply_text("❌ Akses ditolak.")
            return

        user_message = update.message.text

        async with aiosqlite.connect(self.db_path) as db:
            provider, model_name = await get_user_model(db, user_id)

        if not self.agent.model_router or self.agent.model_router.provider != provider or self.agent.model_router.model_name != model_name:
            await self.agent.init_model(provider, model_name)

        await update.message.chat.send_action("typing")

        try:
            response = await self.agent.chat(user_id, user_message)
            if len(response) > 4096:
                for i in range(0, len(response), 4096):
                    await update.message.reply_text(response[i:i+4096])
            else:
                await update.message.reply_text(response)
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

        keyboard = [
            [InlineKeyboardButton("🔍 Riset Mitra", callback_data="rnd_riset")],
            [InlineKeyboardButton("📈 Analisis SWOT", callback_data="rnd_swot")],
            [InlineKeyboardButton("📋 Buat Proposal", callback_data="rnd_proposal")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Modul R&D:", reply_markup=reply_markup)

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

    async def module_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        callback_data = query.data
        user_id = query.from_user.id

        if callback_data.startswith("sek_"):
            feature = callback_data.split("_")[1]
            await query.edit_message_text(f"⏳ Fitur sekretaris: {feature} akan segera diimplementasikan!")

        elif callback_data.startswith("rnd_"):
            feature = callback_data.split("_")[1]
            await query.edit_message_text(f"⏳ Fitur R&D: {feature} akan segera diimplementasikan!")

        elif callback_data.startswith("sosmed_"):
            feature = callback_data.split("_")[1]
            await query.edit_message_text(f"⏳ Fitur Social Media: {feature} akan segera diimplementasikan!")

        elif callback_data.startswith("res_"):
            feature = callback_data.split("_")[1]
            await query.edit_message_text(f"⏳ Fitur Resources: {feature} akan segera diimplementasikan!")

        elif callback_data.startswith("auto_"):
            feature = callback_data.split("_")[1]
            await query.edit_message_text(f"⏳ Fitur Automation: {feature} akan segera diimplementasikan!")

    def setup_handlers(self, app: Application):
        app.add_handler(CommandHandler("start", self.start))
        app.add_handler(CommandHandler("help", self.help_cmd))
        app.add_handler(CommandHandler("settings", self.settings))
        app.add_handler(CommandHandler("sek", self.sekretaris))
        app.add_handler(CommandHandler("sekretaris", self.sekretaris))
        app.add_handler(CommandHandler("rnd", self.rnd))
        app.add_handler(CommandHandler("sosmed", self.sosmed))
        app.add_handler(CommandHandler("resources", self.resources))
        app.add_handler(CommandHandler("rag", self.resources))
        app.add_handler(CommandHandler("auto", self.automation))

        app.add_handler(CallbackQueryHandler(self.provider_callback, pattern="^provider_"))
        app.add_handler(CallbackQueryHandler(self.model_callback, pattern="^model_"))
        app.add_handler(CallbackQueryHandler(self.module_callback, pattern="^(sek_|rnd_|sosmed_|res_|auto_)"))

        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.text_message))
