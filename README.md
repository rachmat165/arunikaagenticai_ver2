# REFLECTIVE KOALA — ATG AI Agent Ver2

Telegram-based AI operations agent for PT. Arunika Teknologi Global (ATG).

## Quick Start

### Installation

\\\ash
# Clone repository
git clone <repo-url> D:\ArunikaAgenticAi_Ver2
cd D:\ArunikaAgenticAi_Ver2

# Create virtual environment
python -m venv venv
.\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Setup environment
cp .env.example .env.local
# Edit .env.local with your API keys
\\\

### Configuration

1. Create Telegram Bot via @BotFather
2. Add TELEGRAM_BOT_TOKEN to .env.local
3. Set TELEGRAM_ALLOWED_USERS with whitelist of user IDs
4. Configure Claude API key (ANTHROPIC_API_KEY)

### Running the Bot

\\\ash
python src/main.py
\\\

Bot is now running. Send /start in Telegram to begin.

## 5 Modules

| Command | Module | Purpose |
|---------|--------|---------|
| /sek | Sekretaris | Create docs, presentations, schedule |
| /rnd | R&D | Research partners, generate proposals |
| /sosmed | Social Media | Content creation, analytics |
| /resources | Resources/RAG | Knowledge base management |
| /auto | Automation | Run scripts, schedule jobs |

## Directory Structure

\\\
D:\ArunikaAgenticAi_Ver2\
├── PRD.md                 # Product requirements
├── README.md              # This file
├── ARCHITECTURE.md        # Technical architecture
├── MODULES.md             # Detailed module specs
├── SETUP.md               # Setup guide
├── API_REFERENCE.md       # API documentation
├── ROADMAP.md             # Development roadmap
├── .env.example           # Environment template
├── requirements.txt       # Python dependencies
├── src/
│   ├── main.py           # Entry point
│   ├── agent/            # ATGAgent core
│   ├── modules/          # 5 specialist modules
│   ├── tools/            # Tool implementations
│   └── gateway/          # Telegram gateway
├── data/
│   ├── state.db          # Session store
│   ├── config.yaml       # Settings
│   └── sessions/         # Chat exports
└── docs/
    ├── sekretaris.md     # Sekretaris module spec
    ├── rnd.md            # R&D module spec
    ├── social_media.md   # Social Media spec
    ├── resources.md      # Resources/RAG spec
    └── automation.md     # Automation spec
\\\

## Documentation

- **[PRD.md](PRD.md)** — Full product requirements document
- **[ARCHITECTURE.md](ARCHITECTURE.md)** — Technical architecture & design
- **[MODULES.md](MODULES.md)** — Detailed feature specifications
- **[SETUP.md](SETUP.md)** — Installation & deployment guide
- **[API_REFERENCE.md](API_REFERENCE.md)** — API & tool reference
- **[ROADMAP.md](ROADMAP.md)** — Development roadmap & milestones

## Development

### Prerequisites
- Python 3.11+
- PostgreSQL/Supabase (for RAG)
- Telegram account

### Tech Stack
- **Backend:** Python, FastAPI, Claude API
- **Bot:** python-telegram-bot
- **Database:** SQLite (sessions), Supabase (knowledge base)
- **Documents:** ReportLab (PDF), python-pptx (PPTX)
- **Scheduling:** APScheduler

### Development Workflow

\\\ash
# Activate venv
.\venv\Scripts\activate

# Run tests
pytest tests/

# Run bot in debug mode
DEBUG=1 python src/main.py

# Format code
black src/

# Type check
mypy src/
\\\

## Support

**Owner:** Rachmat A.K. (COO, ATG)  
**Email:** corsec@arunika2045.com  
**Location:** Jl. Calung No. 7, Kota Bandung, Jawa Barat 40223  

## License

Internal use only — PT. Arunika Teknologi Global
