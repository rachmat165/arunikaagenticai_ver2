"""
Modul Karir — evaluasi lowongan, buat CV, riset perusahaan.
Diadaptasi dari Career-Ops (github.com/santifer/career-ops).

Metodologi evaluasi A-F dengan 7 blok analisis terstruktur.
"""

import logging
from src.config import settings
from src.tools.firecrawl import FirecrawlClient

logger = logging.getLogger(__name__)

EVAL_PROMPT = """Kamu adalah pakar evaluasi karir senior menggunakan metodologi Career-Ops.

LOWONGAN YANG DIEVALUASI:
{job_input}

{web_context}

Evaluasi dengan 7 blok analisis terstruktur:

---
**🅐 RINGKASAN POSISI**
- Nama posisi, perusahaan, lokasi, tipe kerja (remote/hybrid/onsite)
- Industri & ukuran perusahaan (startup/SME/enterprise)
- Seniority level yang sebenarnya vs. yang ditulis

**🅑 ANALISIS KESESUAIAN** _(skor 1–5 tiap dimensi)_
| Dimensi | Skor | Catatan |
|---------|------|---------|
| Teknis / Keahlian | /5 | |
| Pengalaman tahun | /5 | |
| Level seniority | /5 | |
| Industri & domain | /5 | |
| Budaya & values | /5 | |

Skor rata-rata: ___/5

**🅒 STRATEGI LEVEL**
- Naik level / lateral / turun level?
- Peluang pertumbuhan 1–3 tahun ke depan
- Leverage untuk negosiasi posisi/level

**🅓 ANALISIS KOMPENSASI**
- Estimasi range gaji (sesuaikan dengan pasar Indonesia/internasional)
- Kompetitif atau di bawah pasar?
- Benefit tambahan yang perlu dikonfirmasi (equity, bonus, remote, dll)

**🅔 RENCANA PERSONALISASI**
- Kata kunci ATS wajib masuk di CV/cover letter
- Pengalaman & pencapaian mana yang paling relevan ditonjolkan
- Narasi utama yang harus dikomunikasikan

**🅕 PERSIAPAN INTERVIEW**
Pertanyaan yang paling mungkin ditanyakan:
1. ...
2. ...
3. ...

Contoh jawaban STAR untuk kompetensi paling kritis:
- **Situasi:** ...
- **Tugas:** ...
- **Aksi:** ...
- **Hasil:** ...

**🅖 PENILAIAN LEGITIMASI**
- Status: ✅ Legitimate / ⚠️ Perlu verifikasi / 🚫 Red flag
- Alasan & tanda-tanda yang ditemukan

---
## 🏆 SKOR AKHIR: [A / B / C / D / E / F]

| Grade | Arti |
|-------|------|
| A | Lamar segera — cocok sekali |
| B | Lanjutkan — perlu sedikit persiapan |
| C | Pertimbangkan — ada kesenjangan |
| D | Lewati kecuali sangat butuh |
| F | Tolak — tidak sesuai atau mencurigakan |

**⚡ REKOMENDASI TINDAK LANJUT:**
Langkah konkret 1-2-3 yang harus dilakukan sekarang.
"""

CV_PROMPT = """Kamu adalah pakar pembuatan CV profesional dengan spesialisasi ATS optimization.

Informasi kandidat:
{user_info}

{target_info}

Buat CV profesional dalam Bahasa Indonesia (atau Inggris jika diminta) dengan panduan:
1. **ATS-optimized**: gunakan kata kunci relevan dari industri/posisi target
2. **Action verbs yang kuat** untuk setiap poin pengalaman
3. **Pencapaian terukur** — kuantifikasi dengan angka/persentase bila memungkinkan
4. **Format bersih** — mudah dibaca manusia dan mesin ATS
5. **Tailored** untuk posisi yang ditarget (jika ada)

Format output dalam Markdown:

---
# [Nama Lengkap]
📧 [email] | 📱 [telepon] | 🔗 LinkedIn | 📍 [kota]

## Ringkasan Profesional
[2-3 kalimat kuat yang menonjolkan nilai unik kandidat]

## Pengalaman Kerja
### [Jabatan] | [Perusahaan] | [Periode]
- [Pencapaian terukur 1]
- [Pencapaian terukur 2]
- [Pencapaian terukur 3]

## Keahlian
**Teknis:** [daftar]
**Soft Skills:** [daftar]
**Tools & Platform:** [daftar]

## Pendidikan
### [Gelar] | [Institusi] | [Tahun]

## Sertifikasi & Pencapaian
- [Sertifikasi/penghargaan jika ada]
---

Setelah CV, tambahkan:
**💡 Tips ATS:** 3 kata kunci tambahan yang disarankan untuk posisi ini.
"""

RISET_PERUSAHAAN_PROMPT = """Kamu adalah konsultan karir yang membantu kandidat mempersiapkan lamaran kerja secara menyeluruh.

Lakukan riset mendalam tentang **{company}** untuk persiapan lamaran:

{web_context}

Sajikan analisis dalam format berikut:

## 🏢 PROFIL PERUSAHAAN: {company}

**Fakta Dasar**
- Tahun berdiri, pendiri, kantor pusat
- Industri & produk/layanan utama
- Ukuran: karyawan & valuasi/revenue (estimasi)
- Stage: startup / scale-up / enterprise / publik (listed)

**Kondisi Bisnis**
- Pertumbuhan & trajectory saat ini
- Funding terbaru (jika startup/scale-up)
- Posisi pasar vs kompetitor utama

**Budaya & Lingkungan Kerja**
- Nilai-nilai yang dipromosikan perusahaan
- Reputasi sebagai employer (Glassdoor/LinkedIn insights)
- Kebijakan remote/hybrid/onsite

**Kepemimpinan**
- CEO/CTO dan background mereka
- Stabilitas kepemimpinan

**Teknologi** _(jika relevan)_
- Tech stack yang digunakan
- Investasi R&D & inovasi

---
## 🎯 PERSIAPAN WAWANCARA

**5 Pertanyaan Cerdas untuk Ditanyakan ke Interviewer:**
1. ...
2. ...
3. ...
4. ...
5. ...

**Poin Koneksi** — bagaimana background kamu relevan dengan misi perusahaan:
- ...

---
## ⚠️ RED FLAGS & PELUANG
- Potensi risiko bergabung: ...
- Peluang pertumbuhan karir: ...

**🌟 Skor Daya Tarik Perusahaan: [X/10]**
Justifikasi: ...
"""

EVOLUSI_PROMPT = """Kamu adalah ahli AI system optimization dan prompt engineering.

Berikut adalah sampel percakapan/log dari bot Telegram AI bernama "Reflective Koala" milik PT. Arunika Teknologi Global:

{conversation_samples}

---
Analisis pola dan berikan laporan perbaikan dalam format:

## 🔍 ANALISIS PERFORMA BOT

**Pola yang Ditemukan:**
- Pertanyaan yang sering ditanyakan user: ...
- Jawaban yang sering kurang memuaskan: ...
- Fitur yang sering digunakan: ...
- Fitur yang jarang digunakan: ...

**Kelemahan yang Teridentifikasi:**
1. [Kelemahan 1] — dampak: [tinggi/sedang/rendah]
2. [Kelemahan 2] — dampak: ...
3. [Kelemahan 3] — dampak: ...

**Peluang Peningkatan:**
1. [Peluang 1] — cara implementasi: ...
2. [Peluang 2] — cara implementasi: ...

## 💡 REKOMENDASI PERBAIKAN KONKRET

**System Prompt yang Disarankan Ditambahkan:**
```
[Tambahan system prompt yang akan meningkatkan kualitas respons]
```

**Perintah Baru yang Direkomendasikan:**
- /<perintah_baru>: [fungsi yang dibutuhkan user]

**Perbaikan Respons untuk Kasus Umum:**
| Pertanyaan Umum | Respons Saat Ini (estimasi) | Respons yang Lebih Baik |
|---|---|---|
| ... | ... | ... |

## 📈 PRIORITAS IMPLEMENTASI (1 = Segera, 3 = Nanti)
1. [Prioritas 1]: ...
2. [Prioritas 2]: ...
3. [Prioritas 3]: ...
"""


class KarirHandler:
    def __init__(self):
        self._fc = (
            FirecrawlClient(settings.firecrawl_api_key)
            if settings.firecrawl_api_key
            else None
        )

    def has_firecrawl(self) -> bool:
        return self._fc is not None

    async def eval_pekerjaan(self, job_input: str, router, on_progress=None) -> str:
        web_context = ""
        # Coba fetch URL jika input berupa link
        if job_input.startswith("http") and self._fc:
            try:
                if on_progress:
                    await on_progress("🔍 Mengambil konten lowongan dari URL...")
                content = await self._fc.scrape(job_input, timeout=20)
                if content:
                    web_context = f"\n\n**Konten dari URL:**\n{content[:4000]}"
            except Exception as e:
                logger.warning("Firecrawl scrape gagal: %s", e)
        elif self._fc:
            # Search web untuk konteks tambahan
            try:
                company_hint = job_input[:80]
                if on_progress:
                    await on_progress("🌐 Mencari informasi tambahan tentang perusahaan...")
                results = await self._fc.search(f"company review glassdoor {company_hint}", limit=2)
                if results:
                    web_context = f"\n\n**Konteks web:**\n{self._fc.format_search_results(results, 1500)}"
            except Exception as e:
                logger.warning("Firecrawl search gagal: %s", e)

        if on_progress:
            await on_progress("🤖 AI sedang mengevaluasi lowongan...")

        prompt = EVAL_PROMPT.format(job_input=job_input, web_context=web_context)
        response, _ = await router.call(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=4096,
        )
        return response

    async def buat_cv(self, user_info: str, job_target: str, router, on_progress=None) -> str:
        target_info = f"\nTarget posisi/perusahaan:\n{job_target}" if job_target else ""
        if on_progress:
            await on_progress("📄 AI sedang menyusun CV profesional...")

        prompt = CV_PROMPT.format(user_info=user_info, target_info=target_info)
        response, _ = await router.call(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=4096,
        )
        return response

    async def riset_perusahaan(self, company: str, router, on_progress=None) -> str:
        web_context = ""
        if self._fc:
            try:
                if on_progress:
                    await on_progress(f"🌐 Mencari informasi tentang {company}...")
                results = await self._fc.search(
                    f"{company} company profile culture review jobs",
                    limit=4,
                )
                if results:
                    web_context = f"\n\nData dari web:\n{self._fc.format_search_results(results, 2000)}"
            except Exception as e:
                logger.warning("Firecrawl riset gagal: %s", e)

        if on_progress:
            await on_progress(f"🏢 AI sedang menganalisis {company}...")

        prompt = RISET_PERUSAHAAN_PROMPT.format(company=company, web_context=web_context)
        response, _ = await router.call(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=4096,
        )
        return response

    async def analisis_evolusi(self, conversation_samples: str, router, on_progress=None) -> str:
        """Analisis performa bot dan saran perbaikan (dari konsep Hermes Evolution)."""
        if on_progress:
            await on_progress("🧬 AI sedang menganalisis pola percakapan untuk saran evolusi bot...")

        prompt = EVOLUSI_PROMPT.format(conversation_samples=conversation_samples)
        response, _ = await router.call(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=4096,
        )
        return response
