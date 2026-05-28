# Modul OTOMATISASI — Detailed Specification

## Overview
Automation module enables Python script execution, job scheduling, and recurring task automation via cron jobs.

## Features

### 1. Run Python Script
**Command:** \/auto run [script_path] [args]\

Execute Python scripts on-demand:
- Whitelist scripts in config
- Pass arguments
- Capture stdout/stderr
- Max 30-minute timeout
- Save logs to E:\Output\logs\

**Example:**
\\\
User: /auto run scripts/weekly_report.py --week 22
Bot: ...executing...
Bot: ✓ Report generated: 120K followers, 8.5% engagement
Bot: Logs saved: E:\Output\logs\weekly_report_20260528.log
\\\

### 2. Schedule Cron Jobs
**Command:** \/auto schedule [script] [cron]\

Create recurring scheduled tasks:
- Cron expression: "0 8 * * 5" (Fri 8 AM)
- Natural language: "every Friday at 8am"
- APScheduler persistent storage
- Auto-execute at scheduled time
- Telegram notification on completion/error

**Cron Expression Examples:**
\\\
"0 8 * * *"        Every day at 8:00 AM
"0 8 * * 1-5"      Weekdays at 8:00 AM
"0 0 1 * *"        First day of month
"*/15 * * * *"     Every 15 minutes
\\\

### 3. Web Scraping Scheduled
**Command:** \/auto scrape [url] [schedule]\

Schedule web scraping tasks:
- Selenium/Playwright for dynamic content
- Run on schedule
- Detect changes vs previous run
- Send summary to Telegram

### 4. Report Generation
**Command:** \/auto report [type] [schedule]\

Auto-generate and deliver reports:
- Weekly/monthly reports
- PDF generation
- Email/Telegram delivery
- Saved to E:\Output\

## Database Schema

\\\sql
CREATE TABLE cron_jobs (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    script_path TEXT,
    schedule TEXT,
    description TEXT,
    next_run TIMESTAMP,
    last_run TIMESTAMP,
    last_result TEXT,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP
);

CREATE TABLE execution_logs (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    executed_at TIMESTAMP,
    duration_seconds INTEGER,
    exit_code INTEGER,
    stdout TEXT,
    stderr TEXT,
    FOREIGN KEY(job_id) REFERENCES cron_jobs(id)
);
\\\

## Integration Points

- APScheduler (job scheduling)
- subprocess (script execution)
- Selenium/Playwright (web scraping)
- Supabase (job storage)
- Telegram (notifications)
- SQLite (execution logs)
