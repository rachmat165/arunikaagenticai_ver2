import httpx
from typing import Optional

FIRECRAWL_BASE = "https://api.firecrawl.dev/v1"


class FirecrawlClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    async def scrape(self, url: str, timeout: int = 30) -> Optional[str]:
        """Scrape a single URL, return markdown content."""
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{FIRECRAWL_BASE}/scrape",
                headers=self.headers,
                json={
                    "url": url,
                    "formats": ["markdown"],
                    "onlyMainContent": True,
                    "removeBase64Images": True,
                },
            )
            if resp.status_code != 200:
                raise RuntimeError(f"Firecrawl scrape error {resp.status_code}: {resp.text[:300]}")
            data = resp.json()
            if not data.get("success"):
                raise RuntimeError(f"Firecrawl gagal: {data}")
            return data.get("data", {}).get("markdown", "")

    async def search(self, query: str, limit: int = 5, timeout: int = 40) -> list[dict]:
        """
        Search the web, return list of {url, title, description, markdown}.
        Each result has scraped markdown content.
        """
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{FIRECRAWL_BASE}/search",
                headers=self.headers,
                json={
                    "query": query,
                    "limit": limit,
                    "scrapeOptions": {
                        "formats": ["markdown"],
                        "onlyMainContent": True,
                    },
                },
            )
            if resp.status_code != 200:
                raise RuntimeError(f"Firecrawl search error {resp.status_code}: {resp.text[:300]}")
            data = resp.json()
            if not data.get("success"):
                raise RuntimeError(f"Firecrawl search gagal: {data}")
            return data.get("data", [])

    def format_search_results(self, results: list[dict], max_chars_each: int = 2000) -> str:
        """Format search results into a single context string for Claude."""
        parts = []
        for i, r in enumerate(results, 1):
            title = r.get("title", "Tanpa Judul")
            url = r.get("url", "")
            desc = r.get("description", "")
            content = r.get("markdown", "") or desc
            content = content[:max_chars_each].strip()
            parts.append(f"--- Sumber {i}: {title} ({url}) ---\n{content}")
        return "\n\n".join(parts)
