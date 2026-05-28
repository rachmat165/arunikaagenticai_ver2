# REFLECTIVE KOALA — ATG AI Agent Ver2

## Product Requirements Document (PRD)

**Version:** 2.0.0  
**Release Date:** 2026-05-28  
**Status:** In Development  
**Owner:** PT. Arunika Teknologi Global (ATG)  
**Contact:** corsec@arunika2045.com  
**Location:** D:\ArunikaAgenticAi_Ver2  

---

## 1. Executive Summary

**Reflective Koala** adalah AI Agent terintegrasi berbasis Telegram yang bertindak sebagai asisten operasional komprehensif bagi PT. Arunika Teknologi Global (ATG).

Agent ini menggabungkan **5 fungsi bisnis utama** dalam satu platform yang dapat diakses via Telegram chat, memberikan kemampuan operasional 24/7 dengan dukungan multi-channel (mobile web, Telegram, dan automation cron).

### Visi
Mengotomatisasi dan mempercepat proses bisnis operasional ATG melalui AI yang responsif, terintegrasi, dan mudah digunakan.

### Target Users
- Owner ATG / CEO
- Chief Operating Officer (COO) — Rachmat A.K.
- Chief Marketing Officer (CMO)
- Tim operasional ATG (Sekretaris, R&D, Marketing, Resources)

### Expected Business Impact
- Pengurangan waktu pembuatan dokumen dari 2-3 jam → 5-10 menit
- Otomatisasi riset mitra: 1 hari → 30 menit
- Analisis sosial media real-time tanpa manual review
- Skalabilitas penawaran produk ke mitra tanpa bottleneck SDM

---

## 2. Problem Statement

### Current Challenges
1. **Dokumen & Surat** — Pembuatan surat dinas, proposal, presentasi memakan waktu manual ~2-3 jam per dokumen
2. **Riset Mitra** — Identifikasi dan analisis calon mitra memerlukan riset manual, tidak terstruktur
3. **Konten Sosial Media** — Pembuatan konten IG/TikTok/YouTube masih manual, tidak ada analisis performa real-time
4. **Knowledge Management** — Tidak ada satu sumber kebenaran untuk produk, program, dan dokumentasi ATG
5. **Penjadwalan & Reminder** — Reminder, agenda, notulensi masih menggunakan tool terpisah
6. **Automation** — Tidak ada cara cepat untuk menjalankan script Python untuk tugas-tugas rutin

### Impact on Business
- Overhead operasional tinggi
- Inconsistency dalam dokumen dan presentasi
- Missed opportunities untuk partnership research
- Sulit melacak performance sosial media
- Kurangnya visibility terhadap schedule dan task

---

## 3. Solution Overview

**Reflective Koala** mengintegrasikan 5 modul specialist dalam satu Agent AI yang dapat diakses via:

- **Telegram Bot** (primary interface, mobile-first)
- **Web Dashboard** (mobile responsive, 9:16 viewport)
- **CLI** (untuk automation dan scripting)

Setiap modul menggunakan Claude API (routing otomatis antara Haiku/Sonnet/Opus) untuk intelligence, dengan tools spesifik per modul.

---

## 4. 5 Modul Utama

### Modul 1: SEKRETARIS
**Command:** /sekretaris atau /sek

Fitur:
- Buat surat dinas (PDF letterhead ATG)
- Buat presentasi (PPTX multi-slide)
- Set agenda meeting (Google Calendar API)
- Notulensi meeting (transkripsi audio → PDF)
- Reminder cron otomatis

**User Story:** Sebagai COO, saya bisa mengetik "buat surat ke BSN tentang kemitraan AI" dan mendapat PDF dalam 60 detik.

### Modul 2: R&D (Research & Development)
**Command:** /rnd

Fitur:
- Riset calon mitra (web crawl, profil perusahaan, SWOT)
- Generate proposal penawaran (PDF letterhead)
- Analisis kebutuhan mitra → rekomendasi solusi ATG
- Design brief produk aplikasi (web/Android/iOS)
- Export laporan riset (PDF/PPTX)

**User Story:** "Cari 5 fintech startup potensial di Jawa Barat" → laporan dengan SWOT dalam 5 menit.

### Modul 3: SOCIAL MEDIA
**Command:** /sosmed

Fitur:
- Buat konten IG (caption + hashtag + visual brief)
- Buat skrip TikTok/Reels (narasi, hook, CTA)
- Buat deskripsi YouTube (SEO-optimized)
- Analisis performa konten (reach, engagement, CTR)
- Content calendar (4 minggu planning)

**User Story:** "Buat 5 konten IG minggu ini tentang layanan AI" → 5 captions + visual brief dalam 10 menit.

### Modul 4: RESOURCES (RAG & Knowledge Base)
**Command:** /resources atau /rag

Fitur:
- Upload & indeks dokumen (PDF, DOCX, TXT) ke vector store
- Semantic search atas knowledge base ATG
- CRUD produk & program ATG
- Partner directory management
- Knowledge graph visualization

**User Story:** Upload profile perusahaan → semua modul bisa merujuk dokumen ini via semantic search.

### Modul 5: OTOMATISASI PYTHON
**Command:** /auto

Fitur:
- Run Python script dari Telegram command
- Schedule cron jobs (APScheduler)
- Auto-generate laporan (weekly/monthly)
- Web scraping terjadwal
- Notification alerts ke Telegram

**User Story:** "Jalankan laporan mingguan sosmed setiap Jumat jam 08:00" → eksekusi otomatis dan kirim hasil.

---

## 5. Technical Stack

| Layer | Teknologi |
|-------|-----------|
| **Interface** | Telegram Bot (python-telegram-bot 21.x) |
| **Web** | FastAPI + Jinja2 (mobile 9:16) |
| **Agent Core** | Claude API (Haiku/Sonnet/Opus) |
| **RAG** | Supabase pgvector + Chroma lokal |
| **Session** | SQLite WAL (pola Hermes) |
| **Scheduler** | APScheduler (cron) |
| **Documents** | ReportLab (PDF), python-pptx (PPTX) |
| **APIs** | Meta, TikTok, YouTube, Google Calendar, Firecrawl |
| **Storage** | Local D:\ArunikaAgenticAi_Ver2\data\ |

---

## 6. Success Metrics

| Module | Metric | Target |
|--------|--------|--------|
| **Sekretaris** | Avg doc generation time | < 2 min |
| **R&D** | Research requests/month | 20+ |
| **Social Media** | Calendar compliance | 100% |
| **Resources** | Documents indexed | 100+ |
| **Automation** | Task success rate | 99% |
| **Overall** | User adoption | 5+ users in 2 months |

---

## 7. Roadmap

### Phase 1: MVP (Weeks 1-2)
- Infrastructure setup, Telegram bot template, basic auth
- **Deliverable:** Working Telegram bot with /start command

### Phase 2: Core Features (Weeks 3-5)
- R&D modul (riset, proposal)
- Resources modul (RAG, knowledge base)
- Social Media modul (content creation, analytics)

### Phase 3: Automation & Polish (Weeks 6-8)
- Automation modul (cron, schedule)
- Web interface (mobile dashboard)
- Testing, security, documentation

### Phase 4: Deployment (Weeks 9+)
- Production deployment (VPS/Docker)
- Monitoring setup
- User training

---

## 8. Security

- **Authentication:** Telegram user ID whitelist
- **Authorization:** Role-based access (Owner, COO, CMO, Ops)
- **Data Protection:** Local encryption, audit logging
- **Secrets:** API keys in .env (not in git)
- **Compliance:** GDPR-ready, auto-delete after 90 days

---

**Owner:** Rachmat A.K. (COO, ATG)  
**Email:** corsec@arunika2045.com  
**Address:** Jl. Calung No. 7, Kota Bandung, Jawa Barat 40223  
**Last Updated:** 2026-05-28  
**Status:** APPROVED FOR DEVELOPMENT
