# Modul SEKRETARIS — Detailed Specification

## Overview
Sekretaris module adalah asisten pribadi untuk manajemen dokumen, jadwal, dan administrative tasks bagi C-level executives dan staff operasional ATG.

## Core Features

### 1. Surat (Letter) Generation - P0 Priority
**Command:** \/sek surat [recipient] [topic]\

Generates formal business letters dengan ATG letterhead yang professional dan consisten.

**Process:**
1. Parse recipient + topic dari user message
2. Query Resources module untuk company info
3. Use Claude Sonnet untuk content generation:
   - Opening (formal greeting)
   - Body (specific to topic)
   - Closing dengan call-to-action
   - Signature area untuk COO
4. Render dengan ReportLab:
   - ATG logo (top-left)
   - Company info + address
   - Date (auto-filled)
   - Main content
   - Signature placeholder
5. Save ke E:\Output\surat\[date]_[recipient].pdf
6. Send ke user via Telegram

**Output Format:**
- A4 size, professional letterhead
- Font: Calibri 11pt body, Arial Bold 14pt heading
- Color: ATG primary blue (#0066CC)
- Signature: Rachmat A.K., Direktur Operasional

---

### 2. Presentasi (Presentation) Generation - P0 Priority
**Command:** \/sek presentasi [title] [slides=8]\

Generates multi-slide PPTX dengan design konsisten ATG.

**Features:**
- Customizable slide count (5-50 slides)
- Professional design template
- ATG branding (logo, colors, fonts)
- Automatic outline generation
- Speaker notes per slide
- Flexible layouts (title, bullet, title+image)

**Process:**
1. Parse title + slide count
2. Use Claude Sonnet untuk outline generation
3. Generate content + visual briefs per slide
4. Render dengan python-pptx
5. Apply ATG design system
6. Save + send to user

---

### 3. Notulensi (Meeting Minutes) - P0 Priority
**Command:** \/sek notulensi\

Transcribe, analyze, dan generate structured meeting minutes dalam format PDF.

**Features:**
- Audio upload support (m4a, mp3, wav)
- Auto-transcription via OpenAI Whisper
- Meeting analysis dengan Claude Opus:
  - Extract topics
  - Identify participants
  - Extract key decisions
  - Identify action items (RACI)
- Structured PDF output
- Archive di knowledge base

**Output:**
- Formal notulensi PDF dengan letterhead
- Topics dengan timestamps
- Action items dengan owner + deadline
- TXT copy untuk searchability

---

### 4. Agenda / Calendar - P1 Priority
**Command:** \/sek agenda\

Create calendar events dengan Google Calendar integration.

**Features:**
- Natural language scheduling
- Auto-invite attendees
- Set multiple reminders
- Description auto-fill dari context
- Supabase tracking

---

### 5. Reminder / Cron - P1 Priority
**Command:** \/sek reminder [task] [schedule]\

Create recurring reminders dengan APScheduler.

**Supported Formats:**
- Cron expression: "0 8 * * 5" (Friday 8 AM)
- Natural language: "every Friday at 8am"
- Simple: "daily", "weekly", "monthly"

---

## Technical Architecture

### Tools & Libraries
- **ReportLab:** PDF generation dengan custom graphics
- **python-pptx:** PPTX generation
- **OpenAI Whisper:** Speech-to-text
- **Google Calendar API:** Calendar integration
- **APScheduler:** Job scheduling dengan persistence
- **Claude API:** Content generation (Sonnet/Opus)

### Storage
- SQLite: Session + cron job persistence
- Supabase: Archive documents + search
- E:\Output\: Generated files
- Google Calendar: Cloud events

### Data Flow
\\\
User (Telegram)
    ↓
[Sekretaris Module]
    ├→ Parse Intent
    ├→ Query Resources
    ├→ Claude API (content gen)
    ├→ ReportLab/python-pptx (rendering)
    ├→ Save file
    └→ Send to user
\\\

---

## Database Schema

\\\sql
-- Generated Documents
CREATE TABLE generated_documents (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    type TEXT,  -- surat, presentasi, notulensi
    title TEXT,
    recipient_or_topic TEXT,
    file_path TEXT,
    file_size_bytes INTEGER,
    created_at TIMESTAMP,
    accessed_count INTEGER DEFAULT 0,
    generated_at_seconds INTEGER
);

-- Cron Jobs
CREATE TABLE cron_jobs (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    task TEXT,
    schedule TEXT,  -- Cron expression
    next_run TIMESTAMP,
    last_run TIMESTAMP,
    last_result TEXT,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP
);

-- Calendar Events (tracking only, source is Google)
CREATE TABLE calendar_events (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    google_event_id TEXT,
    title TEXT,
    date_time TIMESTAMP,
    attendees TEXT,
    created_at TIMESTAMP
);

-- Indexes
CREATE INDEX idx_documents_user ON generated_documents(user_id, created_at DESC);
CREATE INDEX idx_cron_next_run ON cron_jobs(next_run);
CREATE INDEX idx_cron_status ON cron_jobs(status, next_run);
\\\

---

## Error Handling

| Scenario | Error Code | Solution |
|----------|-----------|----------|
| No recipient specified | MISSING_PARAM | Prompt user for recipient |
| Document generation timeout | TIMEOUT | Suggest shorter content |
| Calendar auth expired | AUTH_FAILED | Ask user to re-authorize |
| Cron parse error | INVALID_CRON | Show example formats |
| PDF too large | SIZE_EXCEEDED | Suggest splitting content |

---

## Performance Targets

| Task | Target Response | Typical Actual |
|------|-----------------|----------------|
| Generate surat (1-2 pages) | < 120 sec | 60-90 sec |
| Generate presentasi (8-10 slides) | < 180 sec | 120-150 sec |
| Transcribe + analyze notulensi (30 min audio) | < 300 sec | 180-240 sec |
| Create calendar event | < 30 sec | 10-20 sec |
| Parse + validate cron expression | < 10 sec | 1-5 sec |

---

## Integration Points

### Internal
- **Resources Module:** Lookup company info, product details, contact
- **Telegram Gateway:** File upload/download, message delivery
- **SQLite:** Session + job persistence

### External
- **Claude API:** Content generation (Sonnet content, Opus analysis)
- **Google Calendar API:** Event creation, invitations, reminders
- **OpenAI Whisper:** Audio transcription
- **ReportLab:** PDF rendering dengan ATG branding
- **python-pptx:** PPTX generation

---

## User Workflows

### Workflow 1: Create & Send Proposal Letter
\\\
User: /sek surat
Bot: Recipient? 
User: Bank Syariah Nasional
Bot: Topic/Subject?
User: Proposal for AI Banking Partnership
Bot: [Generating...]
Bot: ✓ Surat_20260528_BSN_AI_Partnership.pdf
User: Send to email too
Bot: Email sent to budi@bsn.com
\\\

### Workflow 2: Generate Meeting Presentation
\\\
User: /sek presentasi
Bot: Title?
User: ATG Q2 2026 Roadmap Presentation
Bot: How many slides?
User: 12
Bot: Include speaker notes?
User: yes
Bot: [Generating...]
Bot: ✓ Presentasi_20260528_Q2_Roadmap.pptx (1.2 MB)
\\\

### Workflow 3: Transcribe & Organize Meeting
\\\
User: /sek notulensi
Bot: Upload audio file or paste text
User: [Uploads: meeting_partnership_20260528.m4a - 45 minutes]
Bot: [Transcribing & analyzing...]
Bot: ✓ Notulensi_20260528_ATG_BSN_Partnership.pdf

Content:
Topic: ATG-BSN Partnership Discussion
Participants: Rachmat (ATG), Budi (BSN), Tuti (BSN)
Key Decisions:
  - Proceed dengan POC fase 1
  - Budget: \ untuk 3 months
Action Items:
  [ ] Rachmat: Send tech specs by Jun 1
  [ ] Budi: Allocate BSN resources by Jun 3
\\\

### Workflow 4: Schedule Recurring Reminder
\\\
User: /sek reminder
Bot: Task description?
User: Send weekly report to management
Bot: Schedule? (e.g., "every Friday 3pm")
User: every Friday at 3pm
Bot: ✓ Reminder scheduled
Bot: Next: Friday, May 31 at 3:00 PM
Bot: Will deliver weekly report PDF + summary to Telegram
\\\

---

## Customization Options

### Document Customization
- **Language:** Bahasa Indonesia (default), English, other
- **Tone:** Formal, semi-formal, casual
- **Length:** Short (1 page), Medium (2-3 pages), Long (4+ pages)
- **Style:** Traditional (formal letterhead), Modern (minimalist)

### Calendar Customization
- **Reminders:** 15 min, 30 min, 1 hour, 1 day before
- **Timezone:** Auto-detect from system (customizable)
- **Notifications:** Telegram + email (Google Calendar native)

### Presentation Customization
- **Template:** Professional (default), Minimal, Creative
- **Aspect Ratio:** 16:9 (default), 4:3
- **Color Scheme:** ATG branding (default), custom

---

## Success Metrics

| Metric | Target | KPI |
|--------|--------|-----|
| Avg document generation time | < 2 min | User satisfaction |
| Adoption rate | 90% (7/8 daily users) | Usage volume |
| Error rate | < 1% | Reliability |
| Document accuracy | 95% | Quality review |
| Calendar sync | 100% | Integration health |

---

**Module Owner:** Operations Team  
**Last Updated:** 2026-05-28  
**Status:** Specification Complete, Ready for Implementation
