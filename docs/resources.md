# Modul RESOURCES — Detailed Specification

## Overview
Resources module manages the knowledge base, product catalog, partner directory, and document indexing for semantic search across all other modules.

## Features

### 1. Document Upload & Indexing
**Command:** \/resources upload\

Upload and auto-index documents:
- Supported formats: PDF, DOCX, TXT, Markdown
- Automatic text extraction
- Chunk splitting for embeddings
- Vector storage in Supabase pgvector
- Full-text search (FTS5) on SQLite

**Process:**
1. User uploads file via Telegram
2. Extract text (pypdf, python-docx)
3. Split into 1024-token chunks (LangChain)
4. Generate embeddings (OpenAI 3-small via Supabase)
5. Store in \documents\ table with metadata
6. Index for semantic search

### 2. Semantic Search
**Command:** \/resources search [query]\

Query knowledge base with natural language:
- Input: "fintech solutions for banking"
- Output: Top 5 relevant documents with scores + snippets

**Process:**
1. Generate embedding for query
2. Vector similarity search via pgvector
3. Rank by relevance score (0-1)
4. Return snippets + document metadata

### 3. Product Management
**Command:** \/resources products [action]\

CRUD operations for ATG product catalog:
- Create: name, description, features, pricing
- Read: list, search, details
- Update: edit product info
- Delete: archive product

### 4. Partner Directory
**Command:** \/resources partners [action]\

Manage partner relationships:
- Company name, industry, location
- Contact person details
- Link to profile document (foreign key)
- Search/filter by industry, location

## Database Schema

\\\sql
CREATE TABLE documents (
    id UUID PRIMARY KEY,
    filename TEXT,
    content TEXT,
    embedding VECTOR(1536),
    uploaded_by TEXT,
    uploaded_at TIMESTAMP,
    indexed BOOLEAN,
    metadata JSONB
);

CREATE TABLE products (
    id UUID PRIMARY KEY,
    name TEXT UNIQUE,
    description TEXT,
    features JSONB,
    pricing JSONB,
    created_at TIMESTAMP
);

CREATE TABLE partners (
    id UUID PRIMARY KEY,
    company_name TEXT UNIQUE,
    industry TEXT,
    location TEXT,
    contact_person TEXT,
    profile_doc_id UUID REFERENCES documents(id),
    created_at TIMESTAMP
);
\\\

## Integration Points

- Supabase pgvector (vector storage)
- LangChain (document loaders, text splitters)
- Chroma DB (local fallback)
- All other modules use semantic search for context
