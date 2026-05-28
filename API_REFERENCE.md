# REFLECTIVE KOALA — API Reference

## Telegram Bot Commands

### Global Commands
| Command | Purpose | Parameters |
|---------|---------|-----------|
| /start | Initialize bot, show main menu | None |
| /help | Show help for all modules | [module] |
| /status | Check bot status & API connections | None |
| /settings | Configure bot behavior | [setting] [value] |
| /logs | View recent logs | [lines=50] |
| /feedback | Send feedback to developers | [message] |

### Sekretaris Module (/sek)
| Command | Purpose | Parameters |
|---------|---------|-----------|
| /sek surat | Generate letter | [recipient] [topic] |
| /sek presentasi | Generate presentation | [title] [slides] |
| /sek notulensi | Transcribe & summarize meeting | [audio_file or text] |
| /sek agenda | Set meeting in calendar | [date] [time] [title] |
| /sek reminder | Create recurring reminder | [task] [schedule] |

### R&D Module (/rnd)
| Command | Purpose | Parameters |
|---------|---------|-----------|
| /rnd research | Find partner candidates | [industry] [location] |
| /rnd proposal | Generate proposal for partner | [partner_name] |
| /rnd swot | Analyze company SWOT | [company_name] |
| /rnd design | Create product design brief | [requirements] |

### Social Media Module (/sosmed)
| Command | Purpose | Parameters |
|---------|---------|-----------|
| /sosmed create | Generate social media content | [topic] [platform] [count] |
| /sosmed analytics | View content performance | [date_range] [platform] |
| /sosmed calendar | Plan 4-week content | [theme] |
| /sosmed tiktok | Generate TikTok script | [topic] |

### Resources Module (/resources)
| Command | Purpose | Parameters |
|---------|---------|-----------|
| /resources upload | Upload document to knowledge base | [file] |
| /resources search | Search knowledge base | [query] |
| /resources products | Manage product catalog | [action] [details] |
| /resources partners | Manage partner directory | [action] [details] |

### Automation Module (/auto)
| Command | Purpose | Parameters |
|---------|---------|-----------|
| /auto run | Execute Python script | [script_path] [args] |
| /auto schedule | Create cron job | [script] [schedule] |
| /auto list | List all scheduled jobs | None |
| /auto remove | Remove scheduled job | [job_id] |

---

## Web API Endpoints

### Authentication
\\\
POST /api/auth/login
Body: {"user_id": "123456", "password": "token"}
Response: {"token": "jwt_token", "expires": 3600}
\\\

### Sekretaris Endpoints
\\\
POST /api/sekretaris/surat
Body: {"recipient": "BSN", "topic": "partnership", "content": "..."}
Response: {"file_path": "E:\Output\surat\...pdf", "status": "success"}

POST /api/sekretaris/presentasi
Body: {"title": "AI Solutions", "slides": [...]}
Response: {"file_path": "E:\Output\presentasi\...pptx"}

POST /api/sekretaris/notulensi
Body: {"audio_file": binary, "or_text": "meeting transcript"}
Response: {"summary": "...", "action_items": [...]}
\\\

### R&D Endpoints
\\\
GET /api/rnd/research?industry=fintech&location=Bandung
Response: {"candidates": [...], "count": 5}

POST /api/rnd/proposal
Body: {"partner_id": "...", "product_ids": [...]}
Response: {"file_path": "E:\Output\rnd\...pdf"}
\\\

### Resources Endpoints
\\\
POST /api/resources/upload
Body: {"file": binary, "document_type": "pdf"}
Response: {"document_id": "uuid", "indexed": true}

GET /api/resources/search?query=fintech&limit=5
Response: {"results": [{...}], "total_score": 0.92}

GET /api/resources/products
Response: {"products": [...], "count": 12}

POST /api/resources/products
Body: {"name": "Product A", "description": "..."}
Response: {"product_id": "uuid", "created": true}
\\\

### Automation Endpoints
\\\
POST /api/automation/run
Body: {"script": "scripts/report.py", "args": ["--weekly"]}
Response: {"job_id": "...", "status": "running"}

POST /api/automation/schedule
Body: {"script": "...", "cron": "0 8 * * 5"}
Response: {"job_id": "...", "next_run": "2026-05-29 08:00"}

GET /api/automation/jobs
Response: {"jobs": [...], "count": 5}
\\\

---

## Tool Reference

### DocumentGenerator
\\\python
from src.tools.document_gen import DocumentGenerator

gen = DocumentGenerator()
result = gen.generate_letter(
    recipient="Bank Syariah Nasional",
    topic="AI Partnership Proposal",
    body="...",
    signature_image_path="assets/signature.png"
)
# Returns: PdfFile object
\\\

### PresentationGenerator
\\\python
from src.tools.document_gen import PresentationGenerator

gen = PresentationGenerator()
result = gen.generate_pptx(
    title="AI Solutions for Banking",
    slides=[
        {"title": "Problem", "content": "..."},
        {"title": "Solution", "content": "..."},
    ]
)
# Returns: PptxFile object
\\\

### WebScraper
\\\python
from src.tools.web_scraper import WebScraper

scraper = WebScraper(api_key="firecrawl_key")
result = scraper.scrape_company(
    search_terms="fintech startup Bandung",
    limit=5
)
# Returns: List[CompanyProfile]
\\\

### SemanticSearch
\\\python
from src.tools.search import SemanticSearch

search = SemanticSearch(supabase_client)
results = search.query(
    "fintech solutions for banking",
    limit=5
)
# Returns: List[Document] with relevance scores
\\\

### SchedulerManager
\\\python
from src.tools.automation import SchedulerManager

scheduler = SchedulerManager()
job = scheduler.add_cron_job(
    script_path="scripts/weekly_report.py",
    cron_expression="0 8 * * 5",  # Friday 8 AM
    description="Weekly report"
)
# Returns: Job object with job_id
\\\

---

## Error Codes & Responses

### Success Responses
\\\json
{
  "status": "success",
  "data": {...},
  "timestamp": "2026-05-28T10:30:00Z"
}
\\\

### Error Responses
\\\json
{
  "status": "error",
  "code": "INVALID_INPUT",
  "message": "User ID not in whitelist",
  "details": {...},
  "timestamp": "2026-05-28T10:30:00Z"
}
\\\

### Common Error Codes
| Code | Meaning | Solution |
|------|---------|----------|
| AUTH_FAILED | User not authenticated | Add user_id to whitelist |
| RATE_LIMITED | Too many requests | Wait a few minutes |
| INVALID_INPUT | Bad parameters | Check command syntax |
| API_ERROR | External API failed | Retry or check API status |
| TIMEOUT | Operation took too long | Increase timeout or split task |
| DATABASE_ERROR | SQLite/Supabase error | Check database connectivity |

---

## Rate Limits

- **Telegram Bot:** 30 requests/second per bot
- **Claude API:** Per plan (Haiku ~1M/day, Sonnet ~500K/day, Opus ~100K/day)
- **Supabase:** Per plan (PostgreSQL: 10M/month for free tier)
- **Web API:** 100 requests/hour per user

---

## Authentication

### API Key Format
All API requests require JWT token in header:
\\\
Authorization: Bearer <jwt_token>
\\\

### Obtaining Token
\\\ash
curl -X POST http://localhost:8000/api/auth/login \\
  -H "Content-Type: application/json" \\
  -d '{"user_id": "123456", "password": "token"}'
\\\

### Token Expiry
- JWT tokens expire after 1 hour
- Use refresh endpoint to get new token
- Telegram session tokens auto-refresh

---

## Webhook Callbacks (Optional)

When configured, bot sends callbacks to external webhook:

\\\json
{
  "event": "document_generated",
  "timestamp": "2026-05-28T10:30:00Z",
  "data": {
    "user_id": "123456",
    "command": "/sek surat",
    "result": {
      "file_path": "E:\Output\surat\...pdf",
      "size_bytes": 125000
    }
  }
}
\\\

Supported events: document_generated, research_completed, content_created, job_executed, error_occurred

---

**Document Owner:** Development Team  
**Last Updated:** 2026-05-28  
**API Version:** 2.0.0
