# REFLECTIVE KOALA — Technical Architecture

## System Architecture

\\\
┌────────────────────────────────────────────────────────┐
│         TELEGRAM INTERFACE / WEB DASHBOARD              │
│  /sekretaris  /rnd  /sosmed  /resources  /auto          │
│  Command routing, inline keyboards, file handling       │
└─────────────────┬──────────────────────────────────────┘
                  │ python-telegram-bot (polling/webhook)
                  │
┌─────────────────▼──────────────────────────────────────┐
│              GATEWAY LAYER                              │
│  ┌──────────────────────────────────────────────────┐   │
│  │ SessionManager    │ UserAuth    │ RateLimiter    │   │
│  │ MessageRouter     │ FileHandler │ MenuBuilder    │   │
│  │ PlatformAdapter   │ StateDB                      │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────┬──────────────────────────────────────┘
                  │
┌─────────────────▼──────────────────────────────────────┐
│              AGENT CORE (ATGAgent)                      │
│  ┌──────────────────────────────────────────────────┐   │
│  │ ModuleDispatcher    ContextManager               │   │
│  │ ModelRouter (H/S/O) ToolExecutor                 │   │
│  │ MemoryManager       SessionDB (SQLite WAL)       │   │
│  └──────────────────────────────────────────────────┘   │
└─────┬───────────────┬───────────────────────────────────┘
      │               │
┌─────▼──┐  ┌────────▼─────────────────────────────────┐
│CLAUDE   │  │ TOOL MODULES                             │
│API      │  │ ┌──────────────────────────────────────┐ │
│         │  │ │ Sekretaris Tools                    │ │
│Haiku    │  │ │ - ReportLab (PDF generator)         │ │
│(simple) │  │ │ - python-pptx (presentation gen)    │ │
│         │  │ │ - Google Calendar API               │ │
│Sonnet   │  │ │ - OpenAI Whisper (transcription)    │ │
│(default)│  │ │ - APScheduler (cron)                │ │
│         │  │ ├──────────────────────────────────────┤ │
│Opus     │  │ │ R&D Tools                           │ │
│(complex)│  │ │ - Firecrawl (web scraping)          │ │
│         │  │ │ - ReportLab + python-pptx           │ │
│         │  │ │ - LangChain (semantic search)       │ │
│         │  │ ├──────────────────────────────────────┤ │
│         │  │ │ Social Media Tools                  │ │
│         │  │ │ - Meta Graph API                    │ │
│         │  │ │ - TikTok API                        │ │
│         │  │ │ - YouTube Data API v3               │ │
│         │  │ │ - Image generation (Gemini/DALL-E) │ │
│         │  │ ├──────────────────────────────────────┤ │
│         │  │ │ Resources/RAG Tools                 │ │
│         │  │ │ - Supabase pgvector                 │ │
│         │  │ │ - LangChain document loader         │ │
│         │  │ │ - Chroma (local vector DB)          │ │
│         │  │ │ - Supabase PostgreSQL (CRUD)        │ │
│         │  │ ├──────────────────────────────────────┤ │
│         │  │ │ Automation Tools                    │ │
│         │  │ │ - APScheduler (job scheduling)      │ │
│         │  │ │ - subprocess (script execution)     │ │
│         │  │ │ - Selenium/Playwright (scraping)    │ │
│         │  │ │ - logging (audit trail)             │ │
│         │  │ └──────────────────────────────────────┘ │
│         │  └─────────────────────────────────────────┘
│         │
└─────────┘
`

## Data Storage Architecture

### SQLite (Local Session Store)
`
D:\ArunikaAgenticAi_Ver2\data\state.db
├── sessions (id, user_id, platform, model, created_at, cost)
├── messages (id, session_id, role, content, tool_calls, timestamp)
├── cron_jobs (id, user_id, schedule, action, next_run, status)
└── [FTS5 indexes] (full-text search)
`

### Supabase PostgreSQL (Knowledge Base)
`
documents (id, filename, content, embedding, uploaded_by, indexed)
products (id, name, description, features, pricing)
partners (id, company_name, industry, contact_person, profile_doc_id)
[pgvector indexes] (semantic similarity search)
`

### Local File Storage
`
D:\ArunikaAgenticAi_Ver2\data\
├── state.db (SQLite)
├── .env.local (secrets)
├── config.yaml (settings)
├── embeddings/ (local vector cache)
└── cache/ (temp files)

E:\Output\
├── surat/ (generated letters)
├── presentasi/ (generated PPTX)
├── sosmed/ (social media content)
├── rnd/ (research reports)
├── logs/ (execution logs)
└── cache/ (images, temp)
`

## Module Dependency Graph

\\\
┌───────────────────────────────────────────┐
│         RESOURCES/RAG                      │
│  (Knowledge Base, Embeddings, CRUD)        │
│  Dependencies: None (foundation layer)     │
└─────────┬──────────────────────────────────┘
          │
    ┌─────┴──────────────────────────┐
    │                                 │
┌───▼────────────────┐    ┌──────────▼────────────┐
│  SEKRETARIS        │    │  R&D                  │
│  (Documents)       │    │  (Research, Proposal) │
│  Deps: Resources   │    │  Deps: Resources      │
└───┬────────────────┘    └──────────┬────────────┘
    │                               │
    └───────────────┬───────────────┘
                    │
         ┌──────────▼──────────┐
         │  SOCIAL MEDIA       │
         │  (Content creation) │
         │  Deps: Resources    │
         └─────────────────────┘

┌──────────────────────────────────┐
│  AUTOMATION (Python scripts)     │
│  Deps: All modules (calls them)  │
└──────────────────────────────────┘
`

## API Layer Design

### Telegram Gateway
- Input: Telegram updates (messages, callbacks, files)
- Output: Telegram messages, files, inline keyboards
- Protocol: Telegram Bot API (polling or webhook)
- Concurrency: AsyncIO with python-telegram-bot

### Web API (FastAPI)
- Endpoints per module (/api/sekretaris, /api/rnd, etc.)
- Auth: JWT tokens (user_id-based)
- CORS: Telegram user whitelist
- Rate limiting: 100 req/hour per user

### Tools API (Internal)
- Tool execution framework
- Callback hooks (progress, completion, error)
- Streaming support (for long operations)
- Error handling & retry logic

## Deployment Architecture

### Local Deployment
\\\
Windows/Linux
├── Python 3.11+ venv
├── SQLite database (state.db)
├── FastAPI web server (localhost:8000)
├── Telegram bot (polling mode)
└── APScheduler (background jobs)
`

### Cloud Deployment (Optional)
\\\
VPS / Docker / Heroku
├── Python app container
├── PostgreSQL (Supabase)
├── Vector DB (Supabase pgvector)
├── FastAPI (production WSGI)
├── Telegram webhook
└── Monitoring (logs, metrics)
`

## Security Architecture

### Authentication
- Telegram user_id whitelist in .env
- Role-based access control (RBAC)
- Session tokens (JWT)

### Authorization
- Owner: Full access
- COO: Sekretaris, Resources (read)
- CMO: Social Media, Resources (read)
- Ops: Automation, Resources (read)

### Data Protection
- Secrets in .env.local (not versioned)
- Local encryption (Fernet key)
- Audit logging (all requests)
- Session timeout (1 hour)

## Scaling Considerations

### Database Scaling
- SQLite WAL for concurrent reads
- Batch operations for bulk inserts
- Index optimization (FTS5, pgvector)
- Auto-cleanup of old sessions (90-day retention)

### API Scaling
- Connection pooling (Supabase)
- Rate limiting per user
- Async I/O (FastAPI)
- Caching (Redis optional)

### Storage Scaling
- Local storage: 10GB capacity (1 year data)
- Cloud storage: Supabase (unlimited)
- File cleanup (temp files every 7 days)
