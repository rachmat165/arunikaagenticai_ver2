# REFLECTIVE KOALA — Quick Start Guide

## Setup Cepat (5 menit)

### 1. Clone & Install

```bash
cd D:\ArunikaAgenticAi_Ver2
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Konfigurasi Environment

```bash
cp .env.example .env
```

Edit `.env` dengan nilai yang sesuai:

**Minimal (hanya Claude):**
```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
ANTHROPIC_API_KEY=sk-ant-xxxx
TELEGRAM_ALLOWED_USERS=              # Leave empty to allow all
DEBUG=true
```

**Full (dengan OpenRouter):**
```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
ANTHROPIC_API_KEY=sk-ant-xxxx
OPENROUTER_API_KEY=sk-or-xxxx
```

### 3. Jalankan Bot

```bash
python run.py
```

Expected output:
```
2026-05-28 10:30:00,123 - telegram.ext._application - INFO - Application created
2026-05-28 10:30:01,456 - src.main - INFO - Database initialized at D:\ArunikaAgenticAi_Ver2\data\state.db
2026-05-28 10:30:02,789 - src.main - INFO - Telegram handlers registered
2026-05-28 10:30:03,000 - src.main - INFO - Bot is running!
```

### 4. Test di Telegram

Buka chat dengan bot Anda, kirim:

```
/start
```

Bot akan menampilkan welcome menu. Pilih:
- `/sek` — Modul Sekretaris
- `/rnd` — Modul R&D
- `/sosmed` — Modul Social Media
- `/resources` — Modul Resources (RAG)
- `/auto` — Modul Automation
- `/settings` — Pilih model AI (Anthropic/OpenRouter)

Atau ketik pesan biasa untuk chat dengan AI:
```
halo, siapa namamu?
```

## Memilih Model AI

Ketik `/settings` di Telegram:

1. Pilih **Provider**:
   - 🤖 Anthropic Claude
   - 🌐 OpenRouter

2. Pilih **Model**:
   - Anthropic: Haiku, Sonnet, Opus
   - OpenRouter: GPT-4o, Gemini, Llama, Mistral, Deepseek

Pilihan disimpan per-user di SQLite database.

## Struktur Project

```
D:\ArunikaAgenticAi_Ver2\
├── src/
│   ├── main.py              # Entry point
│   ├── config.py            # Settings & env loading
│   ├── database/init.py     # SQLite schema
│   ├── agent/               # AI core (model_router, context, orchestration)
│   ├── gateway/             # Telegram handlers
│   ├── modules/             # Feature modules (TODO)
│   ├── tools/               # Document generation
│   └── auth/                # User whitelist
├── requirements.txt
├── run.py
├── .env.example
└── data/
    ├── state.db             # SQLite database (auto-created)
    └── config.yaml          # Config file (TODO)
```

## Database Schema

**SQLite (state.db):**
- `sessions` — User sessions & selected model
- `messages` — Chat history per session
- `user_settings` — Model preferences
- `cron_jobs` — Scheduled tasks

Akses:
```bash
sqlite3 data/state.db
> SELECT * FROM sessions;
> SELECT * FROM messages LIMIT 5;
```

## Troubleshooting

### Bot tidak merespons

1. Cek `.env` — pastikan `TELEGRAM_BOT_TOKEN` valid
2. Cek logs — lihat error message di console
3. Restart bot: `Ctrl+C` kemudian `python run.py` lagi

### "ModuleNotFoundError: No module named 'src'"

```bash
# Pastikan Anda di folder project root
cd D:\ArunikaAgenticAi_Ver2
python run.py
```

### OpenRouter error "401 Unauthorized"

```env
OPENROUTER_API_KEY=sk-or-xxxx    # Check format
```

Dapatkan key dari: https://openrouter.ai/keys

### "ANTHROPIC_API_KEY not configured"

```env
ANTHROPIC_API_KEY=sk-ant-xxxx    # Check format & not expired
```

Dapatkan key dari: https://console.anthropic.com/

## Next Steps

- [ ] Implement modul Sekretaris (`src/modules/sekretaris/`)
- [ ] Implement modul R&D (`src/modules/rnd/`)
- [ ] Implement modul Social Media (`src/modules/sosmed/`)
- [ ] Implement modul Resources (`src/modules/resources/`)
- [ ] Implement modul Automation (`src/modules/automation/`)
- [ ] Build FastAPI web dashboard (`src/web/app.py`)
- [ ] Add Supabase RAG integration
- [ ] Deploy ke production

## Useful Commands

```bash
# Lihat struktur database
sqlite3 data/state.db ".tables"
sqlite3 data/state.db ".schema sessions"

# Hapus database (reset)
rm data/state.db

# Run dengan verbose logging
DEBUG=true python run.py

# Check Python version
python --version    # Must be 3.9+
```

## Support

Untuk error atau pertanyaan, lihat:
- [README.md](README.md) — Pengantar umum
- [ARCHITECTURE.md](ARCHITECTURE.md) — Desain teknis
- [API_REFERENCE.md](API_REFERENCE.md) — Referensi API
