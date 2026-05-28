# Modul SOCIAL MEDIA — Detailed Specification

## Overview
Social Media module handles content creation, scheduling, and performance analytics for Instagram, TikTok, Facebook, and YouTube.

## Features

### 1. Content Creation
**Command:** \/sosmed create [topic] [platform] [count]\

Generate unique social media content per platform with optimized captions, hashtags, and visual briefs.

### 2. Analytics Dashboard
**Command:** \/sosmed analytics [platform] [date_range]\

Aggregate metrics across Instagram, TikTok, YouTube, Facebook:
- Reach (impressions)
- Engagement (likes, comments, shares, saves)
- Follower growth
- CTR (click-through rate)
- Top-performing content analysis
- Audience demographics
- Posting time optimization

### 3. Content Calendar
**Command:** \/sosmed calendar [weeks] [theme]\

Plan 4-week content strategy with:
- Weekly themes aligned to marketing goals
- Daily content concepts per platform
- Optimal posting times
- Export to markdown/spreadsheet
- Auto-scheduling via APIs

## Database Schema

\\\sql
CREATE TABLE content_library (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    topic TEXT,
    platform TEXT,
    caption TEXT,
    hashtags TEXT,
    visual_brief JSONB,
    created_at TIMESTAMP,
    status TEXT DEFAULT 'draft'
);

CREATE TABLE scheduled_posts (
    id TEXT PRIMARY KEY,
    content_id TEXT NOT NULL,
    platform TEXT,
    scheduled_at TIMESTAMP,
    posted_at TIMESTAMP,
    status TEXT DEFAULT 'pending'
);
\\\

## Integration Points

- Meta Graph API (Instagram, Facebook)
- TikTok API
- YouTube Data API v3
- Claude API (Sonnet for content generation)
- Supabase (content library storage)
