#!/usr/bin/env python3
"""
Daily Agentic AI & LLM Updates Fetcher
Mengambil update terbaru tentang Agentic AI, LLM, dan mencari video YouTube terkait
Berjalan setiap hari jam 09:00
"""

import requests
import json
import os
from datetime import datetime
from dotenv import load_dotenv
import urllib.parse

load_dotenv()

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
LOG_FILE = "/var/log/agentic_ai_updates.log"

def log_message(message):
    """Simpan log dengan timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}\n"
    print(log_entry.strip())
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, "a") as f:
            f.write(log_entry)
    except Exception as e:
        print(f"Error writing log: {e}")

def search_github_trends():
    """Cari trending repositories tentang Agentic AI"""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        url = "https://api.github.com/search/repositories"
        params = {
            "q": "agentic ai llm agent",
            "sort": "stars",
            "order": "desc",
            "per_page": 5
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        if response.status_code == 200:
            items = response.json().get("items", [])
            repos = []
            for item in items:
                repos.append({
                    "name": item.get("name"),
                    "url": item.get("html_url"),
                    "description": item.get("description", "No description"),
                    "stars": item.get("stargazers_count")
                })
            return repos
    except Exception as e:
        log_message(f"Error fetching GitHub trends: {e}")
    return []

def search_youtube_videos():
    """Cari video YouTube tentang Agentic AI & LLM"""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        search_queries = [
            "Agentic AI",
            "Large Language Models",
            "AI Agents 2024",
            "AutoGPT",
            "Multi-Agent Systems"
        ]
        
        results = []
        for query in search_queries:
            # Gunakan invidious API atau search YouTube melalui Bing
            url = f"https://www.youtube.com/results"
            params = {"search_query": query}
            
            # Note: YouTube memerlukan API key untuk akses resmi
            # Alternatif: scrape dari hasil pencarian (requires BeautifulSoup)
            log_message(f"Searching YouTube for: {query}")
            results.append({
                "query": query,
                "url": f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"
            })
        
        return results
    except Exception as e:
        log_message(f"Error searching YouTube: {e}")
    return []

def search_hacker_news():
    """Cari berita dari Hacker News tentang AI"""
    try:
        url = "https://hacker-news.firebaseio.com/v0/topstories.json"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            top_stories = response.json()[:10]
            ai_news = []
            
            for story_id in top_stories:
                story_url = f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json"
                story_response = requests.get(story_url, timeout=5)
                
                if story_response.status_code == 200:
                    story = story_response.json()
                    title = story.get("title", "")
                    
                    # Filter untuk AI-related stories
                    if any(keyword.lower() in title.lower() for keyword in 
                           ["ai", "llm", "agent", "machine learning", "neural"]):
                        ai_news.append({
                            "title": title,
                            "url": story.get("url", ""),
                            "score": story.get("score", 0),
                            "time": story.get("time", 0)
                        })
            
            return ai_news[:5]
    except Exception as e:
        log_message(f"Error fetching Hacker News: {e}")
    return []

def send_telegram_message(message):
    """Kirim pesan ke Telegram"""
    try:
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
            log_message("❌ Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID in .env")
            return False
        
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }
        
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            log_message("✅ Message sent to Telegram successfully")
            return True
        else:
            log_message(f"❌ Failed to send Telegram message: {response.text}")
            return False
    except Exception as e:
        log_message(f"❌ Error sending Telegram message: {e}")
        return False

def format_telegram_message(github_repos, youtube_videos, hn_news):
    """Format pesan untuk Telegram"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    message = f"""
<b>🤖 DAILY AGENTIC AI & LLM UPDATE</b>
<i>{timestamp}</i>

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>📚 TOP GITHUB PROJECTS</b>
"""
    
    if github_repos:
        for i, repo in enumerate(github_repos, 1):
            message += f"\n{i}. <b>{repo['name']}</b>\n"
            message += f"   ⭐ {repo['stars']} stars\n"
            message += f"   📝 {repo['description'][:100]}...\n"
            message += f"   🔗 <a href='{repo['url']}'>View on GitHub</a>\n"
    else:
        message += "\n❌ No trending projects found\n"
    
    message += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    message += "<b>🎥 YOUTUBE RESOURCES</b>"
    
    if youtube_videos:
        for i, video in enumerate(youtube_videos, 1):
            message += f"\n{i}. <b>{video['query']}</b>\n"
            message += f"   🔗 <a href='{video['url']}'>Search Videos</a>\n"
    else:
        message += "\n❌ No videos found\n"
    
    message += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    message += "<b>📰 HACKER NEWS</b>"
    
    if hn_news:
        for i, news in enumerate(hn_news, 1):
            message += f"\n{i}. <b>{news['title'][:60]}...</b>\n"
            message += f"   👍 {news['score']} points\n"
            if news['url']:
                message += f"   🔗 <a href='{news['url']}'>Read More</a>\n"
    else:
        message += "\n❌ No AI news found\n"
    
    message += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    message += "<i>Next update: Tomorrow 09:00</i>"
    
    return message

def main():
    """Main function"""
    log_message("🚀 Starting Agentic AI & LLM Updates Fetcher...")
    
    try:
        log_message("📊 Fetching GitHub projects...")
        github_repos = search_github_trends()
        log_message(f"✅ Found {len(github_repos)} GitHub projects")
        
        log_message("🎥 Fetching YouTube videos...")
        youtube_videos = search_youtube_videos()
        log_message(f"✅ Found {len(youtube_videos)} YouTube searches")
        
        log_message("📰 Fetching Hacker News...")
        hn_news = search_hacker_news()
        log_message(f"✅ Found {len(hn_news)} Hacker News items")
        
        # Format dan kirim pesan
        message = format_telegram_message(github_repos, youtube_videos, hn_news)
        send_telegram_message(message)
        
        log_message("✅ All tasks completed successfully")
        
    except Exception as e:
        log_message(f"❌ Error in main: {e}")

if __name__ == "__main__":
    main()
