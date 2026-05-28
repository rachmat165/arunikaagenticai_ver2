import aiosqlite
from src.agent.model_router import ModelRouter
from src.agent.context_manager import ContextManager
from src.config import settings
from src.database import get_user_model, log_usage, get_or_create_session, get_all_session_messages, replace_messages_with_summary, count_session_messages

SYSTEM_PROMPT = """Anda adalah REFLECTIVE KOALA, AI Agent komprehensif untuk PT. Arunika Teknologi Global (ATG).
Nama Anda adalah Dewi — asisten AI profesional ATG.

Anda membantu dengan 5 fungsi utama:
1. SEKRETARIS - membuat surat resmi, presentasi, notulensi meeting, agenda, reminder
2. R&D - riset calon mitra ATG, analisis SWOT, proposal bisnis, riset teknologi
3. SOCIAL MEDIA - konten IG/FB/TikTok/YouTube, analisis performa konten
4. RESOURCES - manajemen dokumen, pengetahuan internal (RAG)
5. AUTOMATION - python scripts, cron jobs, otomatisasi workflow

Panduan respons:
- Jika user menyebut "buat surat" → sarankan gunakan /sek
- Jika user menyebut "riset" atau "cari mitra" → sarankan gunakan /rnd
- Jika user menyebut "konten" atau "posting" → sarankan gunakan /sosmed
- Untuk pertanyaan umum → jawab langsung dengan bahasa Indonesia yang ramah dan profesional
- Selalu singkat, jelas, dan actionable
- Panggil user dengan "Pak/Bu" + nama jika diketahui"""


class ATGAgent:
    def __init__(self):
        self.context_manager = ContextManager(settings.database_path)
        self.model_router: ModelRouter = None
        self._current_provider = "anthropic"
        self._current_model = "claude-sonnet-4-6"

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
        await self.context_manager.add_to_context(user_id, "user", user_message)
        messages = await self.context_manager.get_context(user_id, limit=20)

        try:
            text, usage = await self.model_router.call(
                messages=messages,
                system=SYSTEM_PROMPT,
                temperature=0.7,
                max_tokens=4096
            )
            # Save token usage to database
            async with aiosqlite.connect(settings.database_path) as db:
                await log_usage(
                    db, user_id,
                    self._current_provider,
                    self._current_model,
                    usage["input_tokens"],
                    usage["output_tokens"],
                    usage["cost_usd"]
                )
        except Exception as e:
            text = f"⚠️ Gagal menghubungi {self._current_provider}: {str(e)}\n\nCoba ganti model via /settings"

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
