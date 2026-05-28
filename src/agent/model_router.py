import httpx
from typing import Optional, Tuple
from src.config import settings

ANTHROPIC_MODELS = {
    "claude-haiku-4-5-20251001": "Haiku 4.5 (Cepat & Murah)",
    "claude-sonnet-4-6": "Sonnet 4.6 (Seimbang) ⭐",
    "claude-opus-4-7": "Opus 4.7 (Terpintar)",
}

OPENROUTER_MODELS = {
    # ── Reasoning ──────────────────────────────────────────────────────────
    "deepseek/deepseek-r1":              "🧠 Deepseek R1 (Reasoning)",
    "google/gemini-2.5-pro-preview":     "🧠 Gemini 2.5 Pro (Reasoning)",
    # ── Dokumen & Surat ────────────────────────────────────────────────────
    "anthropic/claude-3.5-sonnet":       "✍️ Claude 3.5 Sonnet (Surat/Dok)",
    "openai/gpt-4o":                     "✍️ GPT-4o (Dokumen & Analisis)",
    "qwen/qwen-2.5-72b-instruct":        "✍️ Qwen 2.5 72B (Multibahasa)",
    # ── Presentasi & Konten ────────────────────────────────────────────────
    "openai/gpt-4o-mini":                "📋 GPT-4o Mini (Presentasi Cepat)",
    "google/gemini-2.0-flash-001":       "📋 Gemini 2.0 Flash (Konten Sosmed)",
    # ── Umum & Hemat ──────────────────────────────────────────────────────
    "meta-llama/llama-3.3-70b-instruct": "💬 Llama 3.3 70B (Umum)",
    "mistralai/mistral-large":           "💬 Mistral Large (Umum)",
    "deepseek/deepseek-chat":            "💬 Deepseek Chat (Hemat)",
}

# Model khusus untuk generate gambar (endpoint /v1/images/generations)
OPENROUTER_IMAGE_MODELS = {
    "black-forest-labs/flux-1.1-pro":    "🖼 FLUX 1.1 Pro (Kualitas Terbaik)",
    "black-forest-labs/flux-schnell":    "⚡ FLUX Schnell (Cepat & Murah)",
    "openai/dall-e-3":                   "🎨 DALL-E 3 (Gaya Kreatif)",
}

# LM Studio models are dynamic — fetched from local server at runtime
# This dict is used as fallback when server is offline
LMSTUDIO_MODELS: dict = {}

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
    "deepseek/deepseek-r1":              (0.55, 2.19),
    "google/gemini-2.5-pro-preview":     (1.25, 10.00),
    "anthropic/claude-3.5-sonnet":       (3.00, 15.00),
    "openai/gpt-4o-mini":                (0.15, 0.60),
    "qwen/qwen-2.5-72b-instruct":        (0.56, 0.77),
    # Image models — billed per image, not per token
    "black-forest-labs/flux-1.1-pro":   (0.04, 0.0),
    "black-forest-labs/flux-schnell":   (0.004, 0.0),
    "openai/dall-e-3":                  (0.04, 0.0),
}


def _normalize_lmstudio_base_url(base_url: str) -> str:
    base_url = base_url.rstrip("/")
    if base_url.lower().endswith("/v1"):
        return base_url[:-3]
    return base_url

async def fetch_lmstudio_models(base_url: str = "http://localhost:1234") -> list:
    """Fetch available models from LM Studio local server. Returns list of (id, display_name)."""
    try:
        normalized = _normalize_lmstudio_base_url(base_url)
        async with httpx.AsyncClient(base_url=normalized, timeout=5.0) as client:
            response = await client.get("/v1/models")
            if response.status_code != 200:
                return []
            data = response.json()
            return [(m["id"], m.get("id", m["id"])) for m in data.get("data", [])]
    except Exception:
        return []


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


async def generate_image_openrouter(
    prompt: str,
    model: str = "black-forest-labs/flux-1.1-pro",
    size: str = "1024x1024",
) -> str:
    """Generate image via OpenRouter. Returns image URL."""
    if not settings.openrouter_api_key:
        raise ValueError("OPENROUTER_API_KEY tidak dikonfigurasi di .env")

    async with httpx.AsyncClient(
        base_url=settings.openrouter_base_url,
        headers={
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://arunika2045.com",
            "X-Title": "Reflective Koala ATG",
        },
        timeout=120.0,
    ) as client:
        response = await client.post(
            "/images/generations",
            json={"model": model, "prompt": prompt, "n": 1, "size": size},
        )
        if response.status_code != 200:
            raise RuntimeError(f"OpenRouter image error {response.status_code}: {response.text}")
        data = response.json()
        return data["data"][0]["url"]


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
        elif self.provider == "lmstudio":
            lmstudio_url = getattr(settings, "lmstudio_base_url", "http://localhost:1234")
            lmstudio_url = _normalize_lmstudio_base_url(lmstudio_url)
            self.client = httpx.AsyncClient(
                base_url=lmstudio_url,
                headers={"Content-Type": "application/json"},
                timeout=300.0
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
        elif self.provider == "lmstudio":
            return await self._call_lmstudio(clean_messages, system, temperature, max_tokens)
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

    async def _call_lmstudio(self, messages: list, system: str,
                              temperature: float, max_tokens: int) -> Tuple[str, dict]:
        all_messages = []
        if system:
            all_messages.append({"role": "system", "content": system})
        all_messages.extend(messages)

        response = await self.client.post(
            "/v1/chat/completions",
            json={"model": self.model_name, "max_tokens": max_tokens,
                  "temperature": temperature, "messages": all_messages}
        )
        if response.status_code != 200:
            raise RuntimeError(f"LM Studio error {response.status_code}: {response.text}")

        data = response.json()
        text = data["choices"][0]["message"]["content"]

        usage = data.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)

        return text, {"input_tokens": input_tokens, "output_tokens": output_tokens, "cost_usd": 0.0}

    def get_model_display(self) -> str:
        if self.provider == "anthropic":
            return ANTHROPIC_MODELS.get(self.model_name, self.model_name)
        if self.provider == "lmstudio":
            return f"🖥️ {self.model_name} (Lokal)"
        return OPENROUTER_MODELS.get(self.model_name, self.model_name)
