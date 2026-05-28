import httpx
from typing import Optional
from src.config import settings

ANTHROPIC_MODELS = {
    "claude-3-5-haiku-20241022": "Haiku (Fast, Cheap)",
    "claude-3-5-sonnet-20241022": "Sonnet (Balanced)",
    "claude-opus-4-7": "Opus (Smart, Expensive)",
}

OPENROUTER_MODELS = {
    "gpt-4o": "GPT-4o (OpenAI)",
    "google/gemini-2.0-flash-001": "Gemini 2.0 Flash",
    "meta-llama/llama-3.3-70b-instruct": "Llama 3.3 70B",
    "mistralai/mistral-large": "Mistral Large",
    "deepseek/deepseek-chat": "Deepseek Chat",
}

class ModelRouter:
    def __init__(self, provider: str = "anthropic", model_name: str = "claude-3-5-sonnet-20241022"):
        self.provider = provider
        self.model_name = model_name
        self.client: Optional[httpx.AsyncClient] = None

    async def init_client(self):
        if self.provider == "anthropic":
            self.client = httpx.AsyncClient(
                base_url=settings.anthropic_base_url,
                headers={"x-api-key": settings.anthropic_api_key}
            )
        elif self.provider == "openrouter":
            if not settings.openrouter_api_key:
                raise ValueError("OPENROUTER_API_KEY not configured")
            self.client = httpx.AsyncClient(
                base_url=settings.openrouter_base_url,
                headers={"Authorization": f"Bearer {settings.openrouter_api_key}"}
            )

    async def close_client(self):
        if self.client:
            await self.client.aclose()

    async def call(self, messages: list, temperature: float = 0.7, max_tokens: int = 4096) -> str:
        if not self.client:
            await self.init_client()

        if self.provider == "anthropic":
            return await self._call_anthropic(messages, temperature, max_tokens)
        elif self.provider == "openrouter":
            return await self._call_openrouter(messages, temperature, max_tokens)
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    async def _call_anthropic(self, messages: list, temperature: float, max_tokens: int) -> str:
        response = await self.client.post(
            "/v1/messages",
            json={
                "model": self.model_name,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": messages,
            },
            timeout=60.0
        )
        response.raise_for_status()
        data = response.json()
        return data["content"][0]["text"]

    async def _call_openrouter(self, messages: list, temperature: float, max_tokens: int) -> str:
        response = await self.client.post(
            "/chat/completions",
            json={
                "model": self.model_name,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": messages,
            },
            timeout=60.0
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]

    def get_model_display(self) -> str:
        if self.provider == "anthropic":
            return ANTHROPIC_MODELS.get(self.model_name, self.model_name)
        elif self.provider == "openrouter":
            return OPENROUTER_MODELS.get(self.model_name, self.model_name)
        return self.model_name
