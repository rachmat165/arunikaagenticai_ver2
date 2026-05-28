import httpx
from typing import Optional, Tuple
from src.config import settings

ANTHROPIC_MODELS = {
    "claude-haiku-4-5-20251001": "Haiku 4.5 (Cepat & Murah)",
    "claude-sonnet-4-6": "Sonnet 4.6 (Seimbang) ⭐",
    "claude-opus-4-7": "Opus 4.7 (Terpintar)",
}

OPENROUTER_MODELS = {
    "openai/gpt-4o": "GPT-4o (OpenAI)",
    "google/gemini-2.0-flash-001": "Gemini 2.0 Flash",
    "meta-llama/llama-3.3-70b-instruct": "Llama 3.3 70B",
    "mistralai/mistral-large": "Mistral Large",
    "deepseek/deepseek-chat": "Deepseek Chat",
}

# USD per 1M tokens (input, output)
MODEL_PRICING = {
    "claude-haiku-4-5-20251001": (0.80, 4.00),
    "claude-sonnet-4-6":         (3.00, 15.00),
    "claude-opus-4-7":           (15.00, 75.00),
    # OpenRouter — approximate
    "openai/gpt-4o":                      (5.00, 15.00),
    "google/gemini-2.0-flash-001":        (0.075, 0.30),
    "meta-llama/llama-3.3-70b-instruct":  (0.39, 0.39),
    "mistralai/mistral-large":            (2.00, 6.00),
    "deepseek/deepseek-chat":             (0.27, 1.10),
}


async def fetch_anthropic_models(api_key: str, base_url: str = "https://api.anthropic.com") -> list:
    """Fetch available Claude models from Anthropic API. Returns list of (id, display_name)."""
    async with httpx.AsyncClient(
        base_url=base_url,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        timeout=15.0
    ) as client:
        response = await client.get("/v1/models")
        if response.status_code != 200:
            raise RuntimeError(f"Gagal fetch model: {response.status_code} {response.text}")
        data = response.json()
        models = []
        for m in data.get("data", []):
            model_id = m.get("id", "")
            display = m.get("display_name", model_id)
            if model_id.startswith("claude"):
                models.append((model_id, display))
        # Sort: newest first (by created_at desc, already ordered by API)
        return models


def calc_cost(model_name: str, input_tokens: int, output_tokens: int) -> float:
    pricing = MODEL_PRICING.get(model_name, (3.00, 15.00))
    return (input_tokens * pricing[0] + output_tokens * pricing[1]) / 1_000_000


class ModelRouter:
    def __init__(self, provider: str = "anthropic", model_name: str = "claude-sonnet-4-6"):
        self.provider = provider
        self.model_name = model_name
        self.client: Optional[httpx.AsyncClient] = None

    async def init_client(self):
        if self.provider == "anthropic":
            self.client = httpx.AsyncClient(
                base_url=settings.anthropic_base_url,
                headers={
                    "x-api-key": settings.anthropic_api_key,
                    "Content-Type": "application/json",
                    "anthropic-version": "2023-06-01",
                },
                timeout=120.0
            )
        elif self.provider == "openrouter":
            if not settings.openrouter_api_key:
                raise ValueError("OPENROUTER_API_KEY tidak dikonfigurasi. Atur di file .env")
            self.client = httpx.AsyncClient(
                base_url=settings.openrouter_base_url,
                headers={
                    "Authorization": f"Bearer {settings.openrouter_api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://arunika2045.com",
                    "X-Title": "Reflective Koala ATG",
                },
                timeout=120.0
            )

    async def close_client(self):
        if self.client:
            await self.client.aclose()
            self.client = None

    async def call(self, messages: list, system: str = None,
                   temperature: float = 0.7, max_tokens: int = 4096) -> Tuple[str, dict]:
        """Returns (response_text, usage_dict) where usage_dict has input_tokens, output_tokens, cost_usd."""
        if not self.client:
            await self.init_client()

        # Sanitize messages
        clean_messages = []
        for msg in messages:
            if isinstance(msg, dict) and msg.get("role") and msg.get("content"):
                content = str(msg["content"]).strip()
                if content:
                    clean_messages.append({"role": msg["role"], "content": content})

        # Anthropic requires first message from user
        while clean_messages and clean_messages[0]["role"] == "assistant":
            clean_messages.pop(0)

        if not clean_messages:
            clean_messages = [{"role": "user", "content": "Halo"}]

        if self.provider == "anthropic":
            return await self._call_anthropic(clean_messages, system, temperature, max_tokens)
        elif self.provider == "openrouter":
            return await self._call_openrouter(clean_messages, system, temperature, max_tokens)
        else:
            raise ValueError(f"Provider tidak dikenal: {self.provider}")

    async def _call_anthropic(self, messages: list, system: str,
                               temperature: float, max_tokens: int) -> Tuple[str, dict]:
        payload = {
            "model": self.model_name,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages,
        }
        if system:
            payload["system"] = system

        response = await self.client.post("/v1/messages", json=payload)
        if response.status_code != 200:
            raise RuntimeError(f"Anthropic API error {response.status_code}: {response.text}")

        data = response.json()
        text = data["content"][0]["text"]

        usage = data.get("usage", {})
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        cost = calc_cost(self.model_name, input_tokens, output_tokens)

        return text, {"input_tokens": input_tokens, "output_tokens": output_tokens, "cost_usd": cost}

    async def _call_openrouter(self, messages: list, system: str,
                                temperature: float, max_tokens: int) -> Tuple[str, dict]:
        all_messages = []
        if system:
            all_messages.append({"role": "system", "content": system})
        all_messages.extend(messages)

        response = await self.client.post(
            "/chat/completions",
            json={"model": self.model_name, "max_tokens": max_tokens,
                  "temperature": temperature, "messages": all_messages}
        )
        if response.status_code != 200:
            raise RuntimeError(f"OpenRouter API error {response.status_code}: {response.text}")

        data = response.json()
        text = data["choices"][0]["message"]["content"]

        usage = data.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        cost = calc_cost(self.model_name, input_tokens, output_tokens)

        return text, {"input_tokens": input_tokens, "output_tokens": output_tokens, "cost_usd": cost}

    def get_model_display(self) -> str:
        if self.provider == "anthropic":
            return ANTHROPIC_MODELS.get(self.model_name, self.model_name)
        return OPENROUTER_MODELS.get(self.model_name, self.model_name)
