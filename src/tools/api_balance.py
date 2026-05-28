"""
Cek saldo/kredit real dari masing-masing API provider.
- OpenRouter : GET /api/v1/auth/key  → usage & limit real-time
- Anthropic  : tidak ada endpoint publik → link ke console
- LM Studio  : lokal, tidak ada billing
"""

import httpx
from src.config import settings

IDR_RATE = 16_300   # estimasi USD → IDR


async def check_openrouter_balance() -> dict:
    """
    Cek saldo OpenRouter via /api/v1/auth/key.
    Returns dict dengan keys: usage, limit, remaining, is_free_tier, label, error
    """
    if not settings.openrouter_api_key:
        return {"error": "OPENROUTER_API_KEY tidak dikonfigurasi"}

    try:
        async with httpx.AsyncClient(
            base_url="https://openrouter.ai",
            headers={"Authorization": f"Bearer {settings.openrouter_api_key}"},
            timeout=10.0,
        ) as client:
            resp = await client.get("/api/v1/auth/key")

        if resp.status_code != 200:
            return {"error": f"HTTP {resp.status_code}: {resp.text[:200]}"}

        data = resp.json().get("data", {})
        usage      = float(data.get("usage",       0) or 0)
        limit      = data.get("limit")
        remaining  = (float(limit) - usage) if limit is not None else None
        is_free    = bool(data.get("is_free_tier", False))
        label      = data.get("label", "")

        return {
            "usage":        usage,
            "limit":        float(limit) if limit is not None else None,
            "remaining":    remaining,
            "is_free_tier": is_free,
            "label":        label,
        }

    except httpx.TimeoutException:
        return {"error": "Timeout saat menghubungi OpenRouter"}
    except Exception as e:
        return {"error": str(e)}


async def check_anthropic_balance() -> dict:
    """
    Anthropic tidak menyediakan endpoint publik untuk cek saldo via API key biasa.
    Hanya bisa dicek via dashboard: console.anthropic.com
    Kembalikan info bahwa cek manual diperlukan.
    """
    if not settings.anthropic_api_key:
        return {"error": "ANTHROPIC_API_KEY tidak dikonfigurasi"}

    # Verifikasi key masih valid dengan call minimal
    try:
        async with httpx.AsyncClient(
            base_url=settings.anthropic_base_url,
            headers={
                "x-api-key": settings.anthropic_api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            timeout=10.0,
        ) as client:
            resp = await client.get("/v1/models")

        if resp.status_code == 200:
            key_status = "aktif"
        elif resp.status_code == 401:
            key_status = "invalid/expired"
        else:
            key_status = f"status HTTP {resp.status_code}"

        return {
            "key_status": key_status,
            "note": "Cek saldo di: console.anthropic.com/settings/billing",
        }

    except Exception as e:
        return {"error": str(e)}
