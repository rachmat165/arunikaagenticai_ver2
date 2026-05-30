# 🤖 AGENTIC AI & LLM CRONJOB - SETUP GUIDE

Setup otomatis untuk menjalankan update Agentic AI & LLM setiap hari jam 09:00 dan mengirim ringkasan ke Telegram.

---

## 📋 FILE YANG DIBUAT

```
├── fetch_agentic_ai_updates.py    ← Script utama (Linux/Mac/Windows)
├── setup_cronjob.sh               ← Setup otomatis (Linux/Mac)
├── setup_cronjob.bat              ← Setup otomatis (Windows)
└── SETUP_GUIDE.md                 ← Dokumentasi (file ini)
```

---

## 🔧 SETUP UNTUK LINUX / MAC

### Langkah 1: Persiapkan .env File

Buat file `.env` di direktori yang sama dengan script:

```bash
# .env
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```

**Cara mendapatkan token:**
1. Chat dengan BotFather di Telegram (@BotFather)
2. Gunakan command `/newbot`
3. Ikuti instruksi untuk membuat bot baru
4. Copy token yang diberikan

**Cara mendapatkan Chat ID:**
1. Chat dengan bot Anda
2. Kirim pesan apapun
3. Akses: `https://api.telegram.org/bot{TOKEN}/getUpdates`
4. Lihat `message.chat.id`

### Langkah 2: Jalankan Setup Script

```bash
# Buat script executable
chmod +x setup_cronjob.sh

# Jalankan setup
./setup_cronjob.sh
```

Script akan secara otomatis:
- ✅ Mengecek Python dan requirements
- ✅ Membuat log directory
- ✅ Menambahkan cron entry
- ✅ Memverifikasi instalasi

### Langkah 3: Verifikasi

```bash
# Lihat crontab
crontab -l | grep fetch_agentic_ai_updates

# Test script
python3 fetch_agentic_ai_updates.py

# Lihat logs
tail -f /var/log/agentic_ai_updates.log
```

---

## 🪟 SETUP UNTUK WINDOWS

### Langkah 1: Persiapkan .env File

Buat file `.env` di folder yang sama dengan script:

```
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```

### Langkah 2: Jalankan Setup Script

```cmd
# Klik kanan setup_cronjob.bat
# Pilih "Run as administrator"

REM Atau dari Command Prompt (Run as Admin):
setup_cronjob.bat
```

Script akan secara otomatis:
- ✅ Mengecek Python installation
- ✅ Install Python packages (requests, python-dotenv)
- ✅ Membuat Windows Task Scheduler
- ✅ Memverifikasi instalasi

### Langkah 3: Verifikasi

```cmd
# Lihat task
schtasks /query /tn AgenticAI_LLM_Updates /fo list /v

# Test script
python fetch_agentic_ai_updates.py

# Lihat logs
type %TEMP%\agentic_ai_updates.log
```

---

## ⚙️ MANUAL SETUP (JIKA OTOMATIS GAGAL)

### Linux/Mac - Manual Crontab

```bash
# Edit crontab
crontab -e

# Tambahkan baris ini:
0 9 * * * cd /path/to/script && python3 fetch_agentic_ai_updates.py >> /var/log/agentic_ai_updates.log 2>&1

# Ctrl + O (save)
# Ctrl + X (exit)
```

### Windows - Manual Task Scheduler

1. **Buka Task Scheduler:**
   - Tekan `Windows + R`
   - Ketik `taskschd.msc`
   - Tekan Enter

2. **Create Basic Task:**
   - Klik "Create Basic Task" di panel kanan
   - Nama: `AgenticAI_LLM_Updates`
   - Deskripsi: `Daily Agentic AI & LLM Updates`

3. **Set Trigger:**
   - Pilih "Daily"
   - Set waktu: 09:00

4. **Set Action:**
   - Pilih "Start a program"
   - Program: `C:\path\to\python.exe`
   - Arguments: `"C:\path\to\fetch_agentic_ai_updates.py"`

5. **Finish dan Enable Task**

---

## 📊 CRON SCHEDULE REFERENCE

Format: `minute hour day month weekday`

```
0 9 * * *      ← Setiap hari jam 09:00 (SETUP SAAT INI)
0 */6 * * *    ← Setiap 6 jam
0 9 * * 1-5    ← Hari kerja jam 09:00
0 9,17 * * *   ← Jam 09:00 dan 17:00
```

Untuk edit schedule, gunakan:
```bash
crontab -e     # Edit
crontab -l     # View
crontab -r     # Remove
```

---

## 🧪 TESTING

### Test Script Secara Manual

```bash
# Linux/Mac
python3 fetch_agentic_ai_updates.py

# Windows
python fetch_agentic_ai_updates.py
```

Expected output:
```
[2024-01-15 14:30:45] 🚀 Starting Agentic AI & LLM Updates Fetcher...
[2024-01-15 14:30:46] 📊 Fetching GitHub projects...
[2024-01-15 14:30:48] ✅ Found 5 GitHub projects
[2024-01-15 14:30:49] 🎥 Fetching YouTube videos...
[2024-01-15 14:30:50] ✅ Found 5 YouTube searches
[2024-01-15 14:30:51] 📰 Fetching Hacker News...
[2024-01-15 14:31:05] ✅ Found 5 Hacker News items
[2024-01-15 14:31:10] ✅ Message sent to Telegram successfully
[2024-01-15 14:31:10] ✅ All tasks completed successfully
```

### Test Telegram Integration

Tambahkan debugging di .env:
```
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_ID=your_chat_id
DEBUG=true
```

---

## 📝 LOGS

### Linux/Mac
```bash
# View logs
tail -f /var/log/agentic_ai_updates.log

# Last 50 lines
tail -n 50 /var/log/agentic_ai_updates.log

# Search for errors
grep "❌" /var/log/agentic_ai_updates.log
```

### Windows
```cmd
# View logs
type %TEMP%\agentic_ai_updates.log

# Last 10 lines (PowerShell)
Get-Content $env:TEMP\agentic_ai_updates.log -Tail 10
```

---

## 🐛 TROUBLESHOOTING

### ❌ "Python not found"
```bash
# Linux/Mac
which python3
python3 --version

# Windows
python --version
py --version
```

**Solusi:** Install Python dari https://www.python.org/

### ❌ "Module not found: requests"
```bash
# Linux/Mac
python3 -m pip install requests python-dotenv

# Windows
pip install requests python-dotenv
```

### ❌ "Permission denied" (Linux/Mac)
```bash
chmod +x fetch_agentic_ai_updates.py
chmod +x setup_cronjob.sh
```

### ❌ "Telegram message not sent"
- Verifikasi TELEGRAM_BOT_TOKEN di .env
- Verifikasi TELEGRAM_CHAT_ID
- Pastikan bot punya akses ke chat

```bash
# Test Telegram API
curl "https://api.telegram.org/botYOUR_TOKEN/getMe"
```

### ❌ "Cron job not running" (Linux/Mac)
```bash
# Check if crontab service running
service cron status

# Restart crontab
service cron restart

# Check syslog
grep CRON /var/log/syslog
```

### ❌ "Task not running" (Windows)
1. Buka Task Scheduler
2. Cari task `AgenticAI_LLM_Updates`
3. Klik kanan → Properties
4. Tab "General" → Check "Run with highest privileges"
5. Tab "Conditions" → Uncheck "Start the task only if idle"
6. Klik "OK"

---

## 🔄 UPDATE SCRIPT

Untuk update script atau menambah fitur:

1. Edit `fetch_agentic_ai_updates.py`
2. Test secara manual: `python3 fetch_agentic_ai_updates.py`
3. Cron job otomatis menggunakan versi terbaru

Tidak perlu setup ulang cronjob.

---

## ❌ REMOVE CRONJOB

### Linux/Mac
```bash
# Edit dan hapus entry
crontab -e
# (cari baris dengan fetch_agentic_ai_updates.py dan delete)

# Atau remove semua
crontab -r
```

### Windows
```cmd
# Command Prompt (Run as Admin)
schtasks /delete /tn AgenticAI_LLM_Updates /f

# Atau dari Task Scheduler
# Klik kanan task → Delete
```

---

## 📌 WHAT THE SCRIPT DOES

Setiap hari jam 09:00, script akan:

1. **📚 Fetch GitHub Trending Projects**
   - Mencari repositories trending tentang "Agentic AI" & "LLM"
   - Menampilkan top 5 dengan stars dan deskripsi

2. **🎥 Find YouTube Videos**
   - Mencari video tentang Agentic AI
   - Menyediakan search links untuk:
     - Agentic AI
     - Large Language Models
     - AI Agents 2024
     - AutoGPT
     - Multi-Agent Systems

3. **📰 Get Hacker News**
   - Filter top stories yang AI-related
   - Menampilkan judul, URL, dan upvotes

4. **📤 Send to Telegram**
   - Format ringkasan dengan emoji dan formatting
   - Kirim ke chat yang ditentukan di TELEGRAM_CHAT_ID

---

## 📚 REFERENCE

- **GitHub API:** https://docs.github.com/en/rest
- **Telegram Bot API:** https://core.telegram.org/bots/api
- **Cron Syntax:** https://crontab.guru
- **Python Requests:** https://requests.readthedocs.io

---

## 📞 SUPPORT

Jika ada masalah:
1. Check logs (lihat section LOGS di atas)
2. Test script manually (lihat section TESTING)
3. Verify .env file (TELEGRAM_BOT_TOKEN dan TELEGRAM_CHAT_ID)
4. Check internet connection

---

**Status:** ✅ Ready to Use
**Last Updated:** 2024
**Python Version:** 3.6+
**Requirements:** requests, python-dotenv

