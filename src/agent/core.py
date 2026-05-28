from src.agent.model_router import ModelRouter
from src.agent.context_manager import ContextManager
from src.config import settings

class ATGAgent:
    def __init__(self):
        self.context_manager = ContextManager(settings.database_path)
        self.model_router: ModelRouter = None

    async def init_model(self, provider: str = "anthropic", model_name: str = "claude-3-5-sonnet-20241022"):
        self.model_router = ModelRouter(provider, model_name)
        await self.model_router.init_client()

    async def chat(self, user_id: int, user_message: str) -> str:
        if not self.model_router:
            await self.init_model()

        await self.context_manager.add_to_context(user_id, "user", user_message)

        context = await self.context_manager.get_context(user_id, limit=20)

        system_prompt = """Anda adalah REFLECTIVE KOALA, AI Agent komprehensif untuk PT. Arunika Teknologi Global (ATG).
Anda membantu dengan 5 fungsi utama:
1. SEKRETARIS - membuat surat, presentasi, notulensi, agenda, reminder
2. R&D - riset mitra, analisis SWOT, proposal
3. SOCIAL MEDIA - konten IG/FB/TikTok, analisis performa
4. RESOURCES - manajemen dokumen, pengetahuan (RAG)
5. AUTOMATION - python scripts, cron jobs

Jika user menyebutkan fungsi spesifik (contoh: "buat surat"), tawarkan untuk menggunakan command /sek, /rnd, /sosmed, /resources, /auto.
Untuk pertanyaan umum, jawab dengan singkat dan kontekstual.
Selalu ramah dan profesional."""

        messages = [{"role": role, "content": content} for role, content in context]

        try:
            response = await self.model_router.call(
                messages=messages,
                temperature=0.7,
                max_tokens=4096
            )
        except Exception as e:
            response = f"Error calling {self.model_router.provider}: {str(e)}"

        await self.context_manager.add_to_context(user_id, "assistant", response)
        return response

    async def close(self):
        if self.model_router:
            await self.model_router.close_client()
