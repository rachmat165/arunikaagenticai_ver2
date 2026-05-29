"""
Modul Agen Otonom — multi-step task planning dan eksekusi.
Diadaptasi dari CowAgent (github.com/zhayujie/CowAgent).

Alur: Plan → Research (tools) → Synthesize → Deliver
"""

import logging
import json
from typing import Optional, Callable
from src.config import settings
from src.tools.firecrawl import FirecrawlClient

logger = logging.getLogger(__name__)

PLAN_PROMPT = """Kamu adalah agen AI otonom yang akan menyelesaikan tugas berikut:

TUGAS: {task}

Buat rencana eksekusi dalam format JSON berikut (HANYA JSON, tanpa penjelasan lain):
{{
  "goal": "tujuan utama tugas",
  "steps": [
    {{
      "id": 1,
      "action": "search|scrape|analyze|write",
      "description": "deskripsi langkah",
      "query": "query pencarian atau URL (jika search/scrape)"
    }},
    ...
  ],
  "max_steps": 4
}}

Batasi maksimal 4 langkah. Gunakan action "search" untuk mencari info, "scrape" untuk baca URL spesifik, "analyze" untuk proses data, "write" untuk buat output akhir.
"""

SYNTHESIZE_PROMPT = """Kamu adalah agen AI otonom yang telah mengumpulkan data untuk menyelesaikan tugas berikut:

TUGAS AWAL: {task}

RENCANA YANG DIJALANKAN:
{plan_summary}

DATA YANG TERKUMPUL:
{gathered_data}

Sekarang buat output akhir yang komprehensif, terstruktur, dan actionable dalam Bahasa Indonesia.
Gunakan heading, bullet points, dan format yang mudah dibaca.
Sertakan sumber informasi di bagian akhir jika ada.
"""


class AgenHandler:
    def __init__(self):
        self._fc = (
            FirecrawlClient(settings.firecrawl_api_key)
            if settings.firecrawl_api_key
            else None
        )

    def has_firecrawl(self) -> bool:
        return self._fc is not None

    async def run(
        self,
        task: str,
        router,
        on_progress: Optional[Callable] = None,
    ) -> str:
        """
        Jalankan agen otonom multi-step:
        1. Buat rencana
        2. Eksekusi tiap langkah dengan tools
        3. Sintesis hasil akhir
        """
        # ── Step 1: Planning ────────────────────────────────────────────────
        if on_progress:
            await on_progress(
                f"🤖 *Agen Otonom*\n\n"
                f"📋 *Tugas:* `{task[:100]}`\n\n"
                f"⏳ *Step 1/3* — Membuat rencana eksekusi..."
            )

        plan_resp, _ = await router.call(
            messages=[{"role": "user", "content": PLAN_PROMPT.format(task=task)}],
            temperature=0.3,
            max_tokens=1024,
        )

        # Parse JSON plan
        plan = None
        try:
            json_start = plan_resp.find("{")
            json_end = plan_resp.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                plan = json.loads(plan_resp[json_start:json_end])
        except Exception:
            pass

        if not plan or not plan.get("steps"):
            # Fallback: jalankan sebagai query langsung
            if on_progress:
                await on_progress("⚡ Mode langsung (tanpa rencana multi-step)...")
            response, _ = await router.call(
                messages=[{"role": "user", "content": task}],
                temperature=0.3,
                max_tokens=4096,
            )
            return response

        steps = plan["steps"][: plan.get("max_steps", 4)]
        goal = plan.get("goal", task)

        # ── Step 2: Execute steps ───────────────────────────────────────────
        gathered_data = []
        plan_summary_lines = [f"Tujuan: {goal}"]

        for i, step in enumerate(steps, 1):
            action = step.get("action", "analyze")
            desc = step.get("description", "")
            query = step.get("query", "")

            if on_progress:
                await on_progress(
                    f"🤖 *Agen Otonom*\n\n"
                    f"📋 Tugas: `{task[:80]}`\n\n"
                    f"⏳ *Step {i}/{len(steps)+1}* — {desc}"
                )

            plan_summary_lines.append(f"  {i}. [{action}] {desc}")

            if action == "search" and query and self._fc:
                try:
                    results = await self._fc.search(query, limit=3)
                    if results:
                        content = self._fc.format_search_results(results, 2000)
                        gathered_data.append(f"### Hasil Pencarian: {query}\n{content}")
                    else:
                        gathered_data.append(f"### {desc}\nTidak ada hasil pencarian.")
                except Exception as e:
                    logger.warning("Agen search gagal: %s", e)
                    gathered_data.append(f"### {desc}\nSearch gagal: {e}")

            elif action == "scrape" and query and self._fc:
                try:
                    url = query if query.startswith("http") else f"https://{query}"
                    content = await self._fc.scrape(url, timeout=25)
                    if content:
                        gathered_data.append(f"### Konten dari {url}\n{content[:3000]}")
                except Exception as e:
                    logger.warning("Agen scrape gagal: %s", e)
                    gathered_data.append(f"### {desc}\nScrape gagal: {e}")

            elif action in ("analyze", "write"):
                # AI-only step — tidak butuh external tools
                if query:
                    sub_resp, _ = await router.call(
                        messages=[{"role": "user", "content": f"Konteks tugas: {task}\n\n{query}"}],
                        temperature=0.3,
                        max_tokens=2048,
                    )
                    gathered_data.append(f"### {desc}\n{sub_resp}")

        # ── Step 3: Synthesize ──────────────────────────────────────────────
        if on_progress:
            await on_progress(
                f"🤖 *Agen Otonom*\n\n"
                f"📋 Tugas: `{task[:80]}`\n\n"
                f"⏳ *Step {len(steps)+1}/{len(steps)+1}* — Menyintesis hasil..."
            )

        combined_data = "\n\n".join(gathered_data) if gathered_data else "Tidak ada data eksternal."
        plan_summary = "\n".join(plan_summary_lines)

        final_resp, _ = await router.call(
            messages=[{
                "role": "user",
                "content": SYNTHESIZE_PROMPT.format(
                    task=task,
                    plan_summary=plan_summary,
                    gathered_data=combined_data[:8000],
                ),
            }],
            temperature=0.3,
            max_tokens=4096,
        )
        return final_resp
