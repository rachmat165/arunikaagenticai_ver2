import logging
from typing import Optional
from src.config import settings
from src.tools.firecrawl import FirecrawlClient
from src.agent.model_router import ModelRouter

logger = logging.getLogger(__name__)

# ── Prompt templates ──────────────────────────────────────────────────────────

RISET_MITRA_PROMPT = """Anda adalah analis bisnis senior PT. Arunika Teknologi Global (ATG).
ATG adalah perusahaan teknologi Indonesia yang fokus pada solusi AI, digital transformation, dan pengembangan aplikasi berbasis AI untuk berbagai sektor.

TUGAS: Buat laporan riset calon mitra bisnis yang komprehensif tentang: **{subject}**

DATA RISET DARI WEB:
{web_data}

Buat laporan dengan format berikut (gunakan Bahasa Indonesia profesional):

## 📊 LAPORAN RISET MITRA
### {subject}

**1. PROFIL PERUSAHAAN**
- Nama resmi, tahun berdiri, skala (startup/SME/enterprise)
- Bidang usaha & industri
- Lokasi & jangkauan operasional

**2. PRODUK & LAYANAN UTAMA**
- Daftar produk/layanan utama
- Target market / customer segment

**3. POTENSI KEMITRAAN DENGAN ATG**
- Skor Potensi: ⭐/10
- Alasan & justifikasi
- Kebutuhan yang bisa dipenuhi ATG

**4. AREA KOLABORASI YANG DIREKOMENDASIKAN**
- Proyek AI / digitalisasi yang relevan
- Model kemitraan (reseller, co-development, white-label, dll)

**5. KONTAK & PENDEKATAN**
- Divisi yang perlu dihubungi
- Strategi pendekatan awal

**6. RISIKO & CATATAN**
- Potensi kendala
- Hal yang perlu diverifikasi lebih lanjut

**7. REKOMENDASI LANGKAH SELANJUTNYA**
- 3 aksi konkret yang bisa dilakukan minggu ini"""

SWOT_PROMPT = """Anda adalah konsultan strategi senior untuk PT. Arunika Teknologi Global (ATG).
ATG adalah perusahaan AI/tech Indonesia yang ingin mengembangkan portofolio klien dan mitra.

TUGAS: Buat analisis SWOT komprehensif untuk: **{subject}**

DATA KONTEKS:
{web_data}

Buat analisis dengan format berikut:

## 🔍 ANALISIS SWOT
### {subject}

```
┌─────────────────────────────┬─────────────────────────────┐
│      STRENGTHS (S)          │      WEAKNESSES (W)         │
│ (Kekuatan Internal)         │ (Kelemahan Internal)        │
├─────────────────────────────┼─────────────────────────────┤
│ • [poin 1]                  │ • [poin 1]                  │
│ • [poin 2]                  │ • [poin 2]                  │
│ • [poin 3]                  │ • [poin 3]                  │
├─────────────────────────────┼─────────────────────────────┤
│     OPPORTUNITIES (O)       │       THREATS (T)           │
│ (Peluang Eksternal)         │ (Ancaman Eksternal)         │
├─────────────────────────────┼─────────────────────────────┤
│ • [poin 1]                  │ • [poin 1]                  │
│ • [poin 2]                  │ • [poin 2]                  │
│ • [poin 3]                  │ • [poin 3]                  │
└─────────────────────────────┴─────────────────────────────┘
```

**STRATEGI REKOMENDASI:**
- **SO (Gunakan kekuatan untuk raih peluang):** ...
- **ST (Gunakan kekuatan untuk hadapi ancaman):** ...
- **WO (Atasi kelemahan lewat peluang):** ...
- **WT (Minimalisir kelemahan & ancaman):** ...

**PRIORITAS TINDAKAN ATG:**
1. [Aksi prioritas 1]
2. [Aksi prioritas 2]
3. [Aksi prioritas 3]"""

PROPOSAL_PROMPT = """Anda adalah Business Development Manager PT. Arunika Teknologi Global (ATG).
ATG adalah perusahaan teknologi Indonesia yang fokus pada solusi AI dan digital transformation.

TUGAS: Buat proposal kemitraan bisnis profesional.

**Mitra:** {partner}
**Jenis Proyek:** {project_type}

DATA PENDUKUNG:
{web_data}

Buat proposal bisnis lengkap:

## 📋 PROPOSAL KEMITRAAN BISNIS
### PT. Arunika Teknologi Global × {partner}

**EXECUTIVE SUMMARY**
[Ringkasan 2-3 kalimat tentang tujuan dan manfaat kemitraan]

**1. LATAR BELAKANG**
- Profil singkat ATG
- Profil singkat {partner}
- Konteks dan urgensi kemitraan

**2. TUJUAN KEMITRAAN**
- Tujuan jangka pendek (0-6 bulan)
- Tujuan jangka panjang (1-3 tahun)

**3. RUANG LINGKUP KERJA SAMA**
- Deliverable utama
- Teknologi/solusi yang akan dikembangkan
- Pembagian peran dan tanggung jawab

**4. MODEL BISNIS**
- Struktur kerja sama (revenue sharing / project-based / joint venture)
- Skema pembayaran
- Proyeksi revenue

**5. TIMELINE & MILESTONE**
| Fase | Aktivitas | Durasi | PIC |
|------|-----------|--------|-----|
| 1    | ...       | ...    | ... |

**6. INVESTASI & ROI**
- Estimasi investasi
- Proyeksi ROI dalam 12 bulan

**7. NEXT STEPS**
1. [Aksi selanjutnya]
2. [Timeline follow-up]
3. [Dokumen yang diperlukan]

---
*Disiapkan oleh: PT. Arunika Teknologi Global*
*Tanggal: {date}*"""

TECH_RESEARCH_PROMPT = """Anda adalah peneliti teknologi senior untuk PT. Arunika Teknologi Global (ATG).
ATG adalah perusahaan AI/tech Indonesia yang selalu mengikuti tren teknologi terkini.

TUGAS: Buat laporan riset teknologi tentang: **{topic}**

DATA DARI WEB (terbaru):
{web_data}

Buat laporan komprehensif:

## 🔬 LAPORAN RISET TEKNOLOGI
### {topic}

**1. OVERVIEW & DEFINISI**
[Penjelasan singkat dan status terkini]

**2. TREN TERKINI (2024-2025)**
- Perkembangan utama
- Player/vendor utama
- Adopsi di Indonesia vs global

**3. USE CASES RELEVAN UNTUK ATG**
- Aplikasi di industri target ATG
- Potensi produk/layanan baru
- Peluang bisnis

**4. PERBANDINGAN TEKNOLOGI**
| Aspek | Opsi A | Opsi B | Opsi C |
|-------|--------|--------|--------|

**5. REKOMENDASI UNTUK ATG**
- Apakah ATG harus adopt teknologi ini?
- Timeline & investasi yang diperlukan
- Risiko dan mitigasi

**6. SUMBER & REFERENSI**
[Daftar sumber yang digunakan]"""

SCRAPE_SUMMARY_PROMPT = """Ringkas konten dari website berikut untuk keperluan riset bisnis ATG:

URL: {url}

KONTEN WEBSITE:
{content}

Buat ringkasan yang mencakup:
1. Tentang perusahaan/website ini
2. Produk/layanan utama
3. Target market
4. Informasi kontak (jika ada)
5. Poin menarik untuk kemitraan dengan ATG"""


class RndHandler:
    """Handles all R&D module logic: research, SWOT, proposals, tech research."""

    def __init__(self):
        self.firecrawl: Optional[FirecrawlClient] = (
            FirecrawlClient(settings.firecrawl_api_key)
            if settings.firecrawl_api_key else None
        )

    def has_firecrawl(self) -> bool:
        return self.firecrawl is not None

    async def _call_claude(self, prompt: str, model_router: ModelRouter) -> str:
        text, _ = await model_router.call(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=4096,
        )
        return text

    async def _web_search(self, query: str, limit: int = 4, on_progress=None) -> str:
        if not self.firecrawl:
            return "(Firecrawl tidak dikonfigurasi — analisis menggunakan pengetahuan Claude)"
        try:
            logger.info(f"Firecrawl search: {query}")
            results = await self.firecrawl.search(query, limit=limit)
            if not results:
                return "(Tidak ada hasil dari web — menggunakan pengetahuan Claude)"
            logger.info(f"Firecrawl returned {len(results)} results")
            if on_progress:
                urls = [r.get("url", "") for r in results[:3]]
                await on_progress(f"🌐 *Step 2/3 — Data ditemukan dari {len(results)} sumber:*\n" +
                                  "\n".join(f"  • `{u[:60]}`" for u in urls) +
                                  "\n\n⏳ *Step 3/3 — Claude sedang menganalisis...*")
            return self.firecrawl.format_search_results(results)
        except Exception as e:
            logger.warning(f"Firecrawl search error: {e}")
            if on_progress:
                await on_progress("⚠️ Web search gagal, Claude menggunakan pengetahuan internal...\n\n⏳ *Step 3/3 — Claude sedang menganalisis...*")
            return f"(Web search tidak tersedia — Claude akan menggunakan pengetahuan internal)"

    async def riset_mitra(self, subject: str, model_router: ModelRouter, on_progress=None) -> str:
        query = f"{subject} perusahaan yayasan Indonesia profil bisnis produk layanan sekolah"
        web_data = await self._web_search(query, on_progress=on_progress)
        prompt = RISET_MITRA_PROMPT.format(subject=subject, web_data=web_data)
        return await self._call_claude(prompt, model_router)

    async def analisis_swot(self, subject: str, model_router: ModelRouter, on_progress=None) -> str:
        query = f"{subject} analisis bisnis kompetitor pasar Indonesia 2024 2025"
        web_data = await self._web_search(query, on_progress=on_progress)
        prompt = SWOT_PROMPT.format(subject=subject, web_data=web_data)
        return await self._call_claude(prompt, model_router)

    async def buat_proposal(self, partner: str, project_type: str, model_router: ModelRouter, on_progress=None) -> str:
        from datetime import date
        query = f"{partner} perusahaan yayasan profil bisnis Indonesia"
        web_data = await self._web_search(query, limit=3, on_progress=on_progress)
        prompt = PROPOSAL_PROMPT.format(
            partner=partner,
            project_type=project_type,
            web_data=web_data,
            date=date.today().strftime("%d %B %Y"),
        )
        return await self._call_claude(prompt, model_router)

    async def riset_teknologi(self, topic: str, model_router: ModelRouter, on_progress=None) -> str:
        query = f"{topic} teknologi terbaru 2024 2025 Indonesia implementasi"
        web_data = await self._web_search(query, on_progress=on_progress)
        prompt = TECH_RESEARCH_PROMPT.format(topic=topic, web_data=web_data)
        return await self._call_claude(prompt, model_router)

    async def scrape_website(self, url: str, model_router: ModelRouter, on_progress=None) -> str:
        if not self.firecrawl:
            return "❌ Firecrawl belum dikonfigurasi. Tambahkan FIRECRAWL_API_KEY di .env"
        try:
            if on_progress:
                await on_progress("🕷️ *Scraping halaman...*\n⏳ Mengambil konten website")
            content = await self.firecrawl.scrape(url)
            if not content:
                return "❌ Tidak ada konten yang bisa diambil dari URL tersebut."
            if on_progress:
                await on_progress(f"✅ Konten berhasil diambil ({len(content):,} karakter)\n\n⏳ *Claude sedang meringkas...*")
            prompt = SCRAPE_SUMMARY_PROMPT.format(url=url, content=content[:6000])
            return await self._call_claude(prompt, model_router)
        except Exception as e:
            return f"❌ Gagal scrape {url}: {e}"
