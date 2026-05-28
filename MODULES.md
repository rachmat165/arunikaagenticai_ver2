# REFLECTIVE KOALA — Module Specifications

## Modul 1: SEKRETARIS

### Overview
Asisten pribadi untuk manajemen dokumen, jadwal, dan administrative tasks.

### Features

#### 1.1 Generate Surat Dinas (P0)
**Input:** Natural language request (e.g., "buat surat penawaran ke BSN tentang AI partnership")  
**Output:** PDF dengan letterhead ATG, format formal, signature placeholder  
**Time Target:** < 2 menit

**Process:**
1. Parse intent dari user message (detect tujuan, topik, detail)
2. Use Claude Sonnet untuk draft content
3. Format dengan ReportLab (logo, letterhead, page layout)
4. Save ke \E:\Output\surat\[date]_[recipient].pdf\
5. Send PDF ke user via Telegram

**Tools:** ReportLab, Jinja2 templates, Supabase (retrieve company info)

#### 1.2 Generate Presentasi (P0)
**Input:** Topic, slides outline, or user description  
**Output:** PPTX multi-slide dengan design konsisten  
**Time Target:** < 3 menit

**Process:**
1. Use Claude Sonnet untuk outline generation (5-10 slides)
2. For each slide: generate title, bullet points, visual brief
3. Use python-pptx untuk build presentation
4. Apply brand colors & fonts (from ATG branding config)
5. Save ke \E:\Output\presentasi\[date]_[topic].pptx\
6. Send PPTX ke user via Telegram

**Tools:** python-pptx, Pillow (image processing), LangChain (outline generation)

#### 1.3 Notulensi Meeting (P0)
**Input:** Audio file (m4a, mp3) or text transcript  
**Output:** Structured markdown/PDF dengan topik, peserta, action items  
**Time Target:** < 2 menit

**Process:**
1. If audio: Use OpenAI Whisper API untuk transcription
2. Use Claude Opus untuk meeting analysis:
   - Extract topics
   - Identify participants
   - Extract action items (RACI)
   - Summarize decisions
3. Format ke structured markdown
4. Convert ke PDF via ReportLab
5. Save ke \E:\Output\surat\[date]_notulensi.pdf\

**Tools:** OpenAI Whisper, Claude Opus, ReportLab, pypdf

#### 1.4 Set Agenda / Calendar Integration (P1)
**Input:** Meeting details (title, date, time, participants, agenda)  
**Output:** Calendar event created + reminder scheduled  

**Process:**
1. Parse meeting details dari user message
2. Create Google Calendar event (via Google Calendar API)
3. Set notification (30 min, 1 day before)
4. Save to SQLite for bot tracking

**Tools:** google-auth, google-auth-oauthlib, google-calendar-api

#### 1.5 Reminder Cron (P1)
**Input:** Task description + recurrence (e.g., "setiap Jumat jam 17:00")  
**Output:** Scheduled reminder delivery to Telegram  

**Process:**
1. Parse recurrence pattern (cron expression)
2. Create cron job in APScheduler
3. At scheduled time: send Telegram message reminder
4. Save job config to SQLite cron_jobs table

**Tools:** APScheduler, APScheduler.triggers.cron

### Error Handling
- Invalid date formats: Suggest correct format
- Missing recipients: Ask for confirmation
- Document generation errors: Return error message with retry option

### Dependencies
- ReportLab (PDF generation)
- python-pptx (presentation generation)
- OpenAI Whisper (speech-to-text)
- Google Calendar API (calendar integration)
- APScheduler (scheduling)

---

## Modul 2: R&D (Research & Development)

### Overview
Research partner companies, analyze needs, generate proposals.

### Features

#### 2.1 Riset Mitra Potensial (P0)
**Input:** Industry, location, company size, key keywords  
**Output:** List of 5-10 candidates dengan profile summary + SWOT  
**Time Target:** < 5 menit

**Process:**
1. Use Firecrawl untuk web scraping hasil Google/LinkedIn
2. For each candidate:
   - Scrape company website
   - Extract company info (size, industry, location, leadership)
   - Collect public info (news, social media)
3. Use Claude Opus untuk SWOT analysis
4. Rank by relevance score
5. Return formatted report

**Tools:** Firecrawl, BeautifulSoup, LangChain, Claude Opus

#### 2.2 Generate Proposal (P0)
**Input:** Partner profile + product details  
**Output:** PDF proposal 3-5 halaman dengan value proposition  
**Time Target:** < 3 menit

**Process:**
1. Retrieve partner info dari Resources module (semantic search)
2. Retrieve ATG product info
3. Use Claude Sonnet untuk proposal content:
   - Executive summary
   - Problem statement (based on partner profile)
   - Solution overview
   - Pricing & timeline
   - Next steps
4. Format dengan ReportLab (letterhead, professional layout)
5. Save ke \E:\Output\rnd\[date]_proposal_[partner].pdf\

**Tools:** ReportLab, LangChain, Claude Sonnet

#### 2.3 Product Design Brief (P1)
**Input:** Partner requirements, type (web/Android/iOS)  
**Output:** Technical design brief untuk development  

**Process:**
1. Analyze partner needs (via semantic search + Claude)
2. Recommend product type & architecture
3. Generate tech stack proposal
4. Create wireframe/mockup descriptions
5. Output as PDF design brief

**Tools:** Claude Opus, Figma API (optional), ReportLab

### Error Handling
- No results found: Broaden search criteria
- Incomplete partner info: Fetch from alternative sources
- API rate limits: Queue requests, retry later

### Dependencies
- Firecrawl (web scraping)
- Claude Opus (analysis)
- ReportLab (PDF generation)
- LangChain (semantic search)

---

## Modul 3: SOCIAL MEDIA

### Overview
Content creation, scheduling, and analytics for Instagram, TikTok, YouTube, Facebook.

### Features

#### 3.1 Content Creation (P0)
**Input:** Topic, platform, number of content pieces  
**Output:** Captions with hashtags + visual brief  
**Time Target:** < 10 menit untuk 5 pieces

**Process:**
1. Use Claude Sonnet untuk caption + hashtag generation
2. For each piece:
   - Generate caption (platform-specific tone)
   - Suggest 5-10 relevant hashtags
   - Create visual brief (color palette, composition, mood)
3. Save to local content database
4. Option to schedule via Buffer/native APIs

**Tools:** Claude Sonnet, LangChain prompts

#### 3.2 Analytics Dashboard (P1)
**Input:** Date range, platform(s)  
**Output:** Aggregated metrics (reach, engagement, CTR)  
**Time Target:** < 1 menit

**Process:**
1. Fetch data dari Meta Graph API, TikTok API, YouTube API
2. Aggregate metrics:
   - Reach (impressions)
   - Engagement (likes, comments, shares)
   - CTR (click-through rate)
   - Top performing content
3. Return formatted dashboard (web or Telegram message)

**Tools:** Meta Graph API, TikTok API, YouTube Data API v3, pandas

#### 3.3 Content Calendar (P1)
**Input:** Duration (weeks/months), themes  
**Output:** Structured calendar dengan posting schedule  

**Process:**
1. Use Claude Sonnet untuk content ideation
2. Create calendar structure (daily/weekly themes)
3. Generate 4-week worth of content concepts
4. Assign posting times (optimal times per platform)
5. Output as markdown table or spreadsheet

**Tools:** Claude Sonnet, openpyxl

### Error Handling
- API auth failures: Prompt to re-authorize
- Rate limits: Queue requests
- Missing platform data: Skip and return partial results

### Dependencies
- Meta Graph API (Instagram, Facebook)
- TikTok API
- YouTube Data API v3
- Claude Sonnet (content generation)

---

## Modul 4: RESOURCES (RAG & Knowledge Base)

### Overview
Manage and search company knowledge base, products, partners.

### Features

#### 4.1 Document Upload & Indexing (P0)
**Input:** PDF, DOCX, TXT files  
**Output:** Indexed documents in vector store  
**Time Target:** < 30 sec per document

**Process:**
1. Accept file upload via Telegram
2. Extract text (pypdf for PDF, python-docx for DOCX)
3. Split text into chunks (LangChain CharacterTextSplitter)
4. Generate embeddings (Supabase pgvector or local Chroma)
5. Store in Supabase documents table
6. Mark as indexed

**Tools:** LangChain, pypdf, python-docx, Supabase

#### 4.2 Semantic Search (P0)
**Input:** Natural language query  
**Output:** Top 5 relevant documents with relevance scores  
**Time Target:** < 5 sec

**Process:**
1. Generate embedding for user query
2. Perform vector similarity search (pgvector)
3. Return top 5 results with scores + snippets
4. All other modules use this for RAG

**Tools:** Supabase pgvector, LangChain vector store

#### 4.3 Product/Program Management (P0)
**Input:** Product name, description, features, pricing (CRUD)  
**Output:** Manage product catalog  

**Process:**
1. Provide Telegram inline menu untuk CRUD operations
2. Store in Supabase products table
3. Make queryable for Sekretaris & R&D modules

**Tools:** Supabase PostgreSQL, SQLAlchemy

#### 4.4 Partner Directory (P1)
**Input:** Partner company info (name, industry, contact, profile doc)  
**Output:** Searchable partner database  

**Process:**
1. Provide CRUD interface (Telegram menu)
2. Link to document (foreign key to documents table)
3. Support filtering by industry, location, etc.

**Tools:** Supabase PostgreSQL

### Error Handling
- Unsupported file type: List supported formats
- Embedding generation error: Retry with fallback
- Search returns no results: Suggest broader query

### Dependencies
- Supabase (PostgreSQL + pgvector)
- LangChain (document loaders, splitters, embeddings)
- Chroma (optional local vector DB)

---

## Modul 5: OTOMATISASI PYTHON

### Overview
Run Python scripts and schedule automated tasks.

### Features

#### 5.1 Run Script On-Demand (P0)
**Input:** Script path + optional arguments  
**Output:** Script execution result + logs  
**Time Target:** Depends on script (max 30 min timeout)

**Process:**
1. Verify script exists + has whitelist permission
2. Execute via subprocess.Popen()
3. Capture stdout + stderr
4. Save logs to \E:\Output\logs\[date]_[script].log\
5. Send result summary to Telegram (truncate if too long)

**Tools:** subprocess, logging, APScheduler

#### 5.2 Schedule Cron Job (P0)
**Input:** Cron expression (e.g., "0 8 * * 5" = every Friday 8:00 AM)  
**Output:** Job created + next run time  

**Process:**
1. Parse cron expression
2. Create APScheduler job
3. Save to SQLite cron_jobs table
4. At scheduled time: execute script
5. Send result to Telegram

**Tools:** APScheduler, APScheduler.triggers.cron

#### 5.3 Auto-Report Generation (P1)
**Input:** Report type (daily/weekly/monthly), delivery method  
**Output:** PDF report generated + sent  

**Process:**
1. Define report templates (weekly sosmed, monthly sales, etc.)
2. Schedule via cron
3. Execute report generation script
4. Convert to PDF
5. Send via Telegram or email

**Tools:** ReportLab, APScheduler, pandas

#### 5.4 Web Scraping Scheduled (P1)
**Input:** URL + scraping rules  
**Output:** Scraped data + summary  

**Process:**
1. Use Selenium or Playwright untuk dynamic content
2. Schedule scraping via cron
3. Compare with previous run (detect changes)
4. Send summary of changes to Telegram

**Tools:** Selenium/Playwright, BeautifulSoup, APScheduler

### Error Handling
- Script execution error: Send error log to user
- Timeout error: Kill process, notify user
- Cron parse error: Suggest correct format

### Dependencies
- APScheduler (job scheduling)
- subprocess (script execution)
- Selenium/Playwright (web scraping)
- logging (audit trail)

---

## Cross-Module Features

### Session Management
- SQLite WAL mode untuk concurrent access
- Auto-cleanup: sessions older than 90 days deleted
- Session export: JSON export of chat history

### Audit Logging
- Log all user actions (user_id, action, timestamp, result)
- Errors logged dengan full stack trace
- Sensitive data (API keys) NOT logged

### Error Recovery
- Automatic retry untuk transient errors (3x with exponential backoff)
- Graceful degradation (partial results if some tools fail)
- User notification untuk critical failures

### Performance Optimization
- Model routing: Haiku untuk simple (50%), Sonnet (35%), Opus (15%)
- Caching: 24-hour cache untuk static data (partner profiles, products)
- Batch operations: Group API calls when possible
