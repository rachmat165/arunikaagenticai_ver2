# REFLECTIVE KOALA — Setup & Installation Guide

## Prerequisites

- **Python:** 3.11 or higher
- **OS:** Windows, macOS, or Linux
- **Internet:** Stable connection (for API calls)
- **Accounts:** Telegram, Anthropic (Claude), Supabase

## Step 1: Environment Setup

### 1.1 Create Virtual Environment

\\\ash
# Windows
python -m venv venv
.\venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
\\\

### 1.2 Install Dependencies

\\\ash
pip install -r requirements.txt
\\\

### 1.3 Copy Environment Template

\\\ash
cp .env.example .env.local
\\\

## Step 2: Configure API Keys

### 2.1 Telegram Bot Token
1. Open Telegram, search for @BotFather
2. Command: /newbot
3. Follow instructions, get \TELEGRAM_BOT_TOKEN\
4. Add to .env.local:
   \\\
   TELEGRAM_BOT_TOKEN=your_token_here
   \\\

### 2.2 Anthropic (Claude) API
1. Go to console.anthropic.com
2. Create API key
3. Add to .env.local:
   \\\
   ANTHROPIC_API_KEY=sk-ant-...
   \\\

### 2.3 Supabase (Knowledge Base)
1. Go to supabase.com
2. Create new project
3. Get URL, API key, service key
4. Add to .env.local:
   \\\
   SUPABASE_URL=https://xxx.supabase.co
   SUPABASE_KEY=your_key
   SUPABASE_SERVICE_KEY=your_service_key
   \\\

### 2.4 Google Calendar (Optional)
1. Go to console.cloud.google.com
2. Create OAuth 2.0 credentials (Desktop app)
3. Download JSON credentials
4. Place in \data/google-creds.json\

### 2.5 Telegram User Whitelist
Get your Telegram user ID:
1. Send message to bot with /start
2. Check logs for your user_id
3. Add to .env.local:
   \\\
   TELEGRAM_ALLOWED_USERS=123456789,987654321
   \\\

### 2.6 Other Optional APIs
- **Meta Graph API:** For Instagram/Facebook
- **TikTok API:** For TikTok integration
- **YouTube API:** For YouTube analytics
- **Firecrawl:** For web scraping
- See .env.example for all options

## Step 3: Database Setup

### 3.1 SQLite (Local Sessions)
Database auto-initializes on first run:
\\\ash
python -c "from src.database import init_db; init_db()"
\\\

### 3.2 Supabase (Knowledge Base)
Run migrations:
\\\ash
python scripts/migrate_supabase.py
\\\

This creates:
- documents table (vector embeddings)
- products table (product catalog)
- partners table (partner directory)
- [FTS5 indexes]

## Step 4: Configuration

### 4.1 Create config.yaml

\\\yaml
# D:\ArunikaAgenticAi_Ver2\data\config.yaml

model:
  provider: "anthropic"
  default_model: "claude-3-5-sonnet-20241022"
  api_key: ""
  base_url: "https://api.anthropic.com"
  context_length: 200000

telegram:
  bot_token: ""
  allowed_users: ""
  polling_timeout: 30
  webhook_url: ""  # Leave empty for polling

compression:
  enabled: true
  threshold: 0.50
  target_ratio: 0.20
  protect_last_n: 20

session_reset:
  mode: "both"  # idle, daily, both, none
  idle_minutes: 1440
  at_hour: 4

memory:
  memory_enabled: true
  character_limit: 50000

agent:
  max_iterations: 60
  verbose: false
  reasoning_effort: "medium"

storage:
  database_path: "D:\\\\ArunikaAgenticAi_Ver2\\\\data\\\\state.db"
  output_dir: "E:\\\\Output"
  cache_ttl_hours: 24
\\\

### 4.2 Create ATG Branding Config

\\\json
# D:\ArunikaAgenticAi_Ver2\data\branding.json

{
  "company": {
    "name": "PT. ARUNIKA TEKNOLOGI GLOBAL",
    "short_name": "ATG",
    "tagline": "Solusi Teknologi Cerdas & Berkelanjutan",
    "address": "Jl. Calung No. 7, Kota Bandung, Jawa Barat 40223",
    "phone": "+62 XXX XXXX XXXX",
    "email": "corsec@arunika2045.com",
    "website": "https://arunika.com"
  },
  "branding": {
    "logo_path": "assets/atg_logo.png",
    "colors": {
      "primary": "#0066CC",
      "secondary": "#00AA44",
      "neutral": "#333333"
    },
    "fonts": {
      "body": "Calibri",
      "heading": "Arial Bold"
    }
  },
  "signature": {
    "name": "Rachmat A.K.",
    "title": "Direktur Operasional",
    "signature_image": "assets/signature.png"
  }
}
\\\

## Step 5: Verify Installation

### 5.1 Health Check

\\\ash
python -m src.health_check
\\\

Expected output:
\\\
✓ Python version: 3.11.x
✓ Claude API: Connected
✓ Telegram Bot: Token valid
✓ Supabase: Connected
✓ Database: SQLite ready
\\\

### 5.2 Test Telegram Connection

\\\ash
python -m src.telegram_test
\\\

Send /start in your Telegram bot, should receive welcome message.

## Step 6: Running the Bot

### 6.1 Development Mode

\\\ash
# With debug logging
DEBUG=1 python src/main.py
\\\

### 6.2 Production Mode

\\\ash
# Quiet logging
python src/main.py
\\\

### 6.3 Background Service (Windows)

\\\ash
# Create service
sc create AtgBot binPath="D:\ArunikaAgenticAi_Ver2\run_bot.bat"
sc start AtgBot

# Stop service
sc stop AtgBot
\\\

### 6.4 Background Service (Linux)

\\\ash
# Create systemd service
sudo cp scripts/atg-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable atg-bot
sudo systemctl start atg-bot

# Check status
sudo systemctl status atg-bot
\\\

## Troubleshooting

### Issue: "TELEGRAM_BOT_TOKEN not found"
- Check .env.local exists in project root
- Verify TELEGRAM_BOT_TOKEN is set
- Ensure no spaces around the value

### Issue: "Cannot connect to Supabase"
- Verify SUPABASE_URL and SUPABASE_KEY
- Check internet connection
- Test with: \curl https://[your-project].supabase.co\

### Issue: "Claude API rate limited"
- Wait a few minutes
- Check API quota at console.anthropic.com
- Consider upgrading plan

### Issue: "Bot doesn't respond to commands"
- Check bot is running: \ps aux | grep main.py\
- Check logs: \	ail -f logs/bot.log\
- Verify user_id is in TELEGRAM_ALLOWED_USERS
- Restart bot: \python src/main.py\

## Next Steps

1. Read [MODULES.md](MODULES.md) untuk memahami setiap modul
2. Customize branding.json dengan logo dan warna perusahaan
3. Upload dokumen ATG ke Resources modul
4. Create scheduled tasks di Automation modul
5. Start using bot commands!

## Support

**Owner:** Rachmat A.K. (COO, ATG)  
**Email:** corsec@arunika2045.com  
**Hours:** Business hours (8 AM - 6 PM Jakarta Time)
