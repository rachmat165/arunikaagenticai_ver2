#!/bin/bash
##################################################################
# SETUP CRONJOB OTOMATIS - AGENTIC AI & LLM UPDATES
# Script ini akan mengatur cronjob untuk menjalankan update harian
# Waktu eksekusi: 09:00 setiap hari
##################################################################

echo "════════════════════════════════════════════════════════════"
echo "🤖 SETUP CRONJOB - AGENTIC AI & LLM UPDATES"
echo "════════════════════════════════════════════════════════════"

# Check if running on Linux/Mac
if [[ "$OSTYPE" != "linux-gnu"* && "$OSTYPE" != "darwin"* ]]; then
    echo "❌ This script only works on Linux/Mac"
    echo "   For Windows, use Windows Task Scheduler"
    exit 1
fi

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_PATH="$SCRIPT_DIR/fetch_agentic_ai_updates.py"
LOG_DIR="/var/log"
LOG_FILE="$LOG_DIR/agentic_ai_updates.log"

echo ""
echo "📋 Configuration:"
echo "   Script: $SCRIPT_PATH"
echo "   Log File: $LOG_FILE"
echo ""

# Check if Python script exists
if [ ! -f "$SCRIPT_PATH" ]; then
    echo "❌ Error: fetch_agentic_ai_updates.py not found at $SCRIPT_PATH"
    exit 1
fi

# Make script executable
chmod +x "$SCRIPT_PATH"
echo "✅ Made script executable"

# Create log directory if it doesn't exist
if [ ! -d "$LOG_DIR" ]; then
    echo "⚠️  Creating log directory: $LOG_DIR"
    sudo mkdir -p "$LOG_DIR"
fi

# Check .env file
if [ ! -f "$SCRIPT_DIR/.env" ]; then
    echo ""
    echo "⚠️  .env file not found!"
    echo "   Create .env file with these variables:"
    echo "   TELEGRAM_BOT_TOKEN=your_token_here"
    echo "   TELEGRAM_CHAT_ID=your_chat_id_here"
    echo ""
    read -p "Do you want to create .env file now? (y/n): " create_env
    if [ "$create_env" = "y" ]; then
        read -p "Enter TELEGRAM_BOT_TOKEN: " bot_token
        read -p "Enter TELEGRAM_CHAT_ID: " chat_id
        cat > "$SCRIPT_DIR/.env" << EOF
TELEGRAM_BOT_TOKEN=$bot_token
TELEGRAM_CHAT_ID=$chat_id
EOF
        echo "✅ .env file created"
    fi
fi

# Get Python path
PYTHON_PATH=$(which python3)
if [ -z "$PYTHON_PATH" ]; then
    PYTHON_PATH=$(which python)
fi

if [ -z "$PYTHON_PATH" ]; then
    echo "❌ Python not found. Please install Python 3"
    exit 1
fi

echo "✅ Using Python: $PYTHON_PATH"

# Check for required Python packages
echo ""
echo "📦 Checking Python packages..."
$PYTHON_PATH -m pip list | grep -q requests
if [ $? -ne 0 ]; then
    echo "⚠️  Installing requests package..."
    $PYTHON_PATH -m pip install requests
fi

$PYTHON_PATH -m pip list | grep -q python-dotenv
if [ $? -ne 0 ]; then
    echo "⚠️  Installing python-dotenv package..."
    $PYTHON_PATH -m pip install python-dotenv
fi

echo "✅ All required packages installed"

# Create cron job entry
CRON_COMMAND="0 9 * * * cd $SCRIPT_DIR && $PYTHON_PATH $SCRIPT_PATH >> $LOG_FILE 2>&1"

echo ""
echo "════════════════════════════════════════════════════════════"
echo "⚙️  ADDING CRONJOB"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "Cron Expression: 0 9 * * *"
echo "Meaning: Every day at 09:00"
echo ""
echo "Cron Command:"
echo "   $CRON_COMMAND"
echo ""

# Check if cron job already exists
TEMP_CRON=$(mktemp)
crontab -l > "$TEMP_CRON" 2>/dev/null || true

if grep -q "fetch_agentic_ai_updates.py" "$TEMP_CRON"; then
    echo "⚠️  Cronjob already exists!"
    echo ""
    read -p "Do you want to remove and recreate it? (y/n): " recreate
    if [ "$recreate" = "y" ]; then
        grep -v "fetch_agentic_ai_updates.py" "$TEMP_CRON" > "$TEMP_CRON.new"
        mv "$TEMP_CRON.new" "$TEMP_CRON"
    else
        echo "❌ Installation cancelled"
        rm "$TEMP_CRON"
        exit 0
    fi
fi

# Add new cron job
echo "$CRON_COMMAND" >> "$TEMP_CRON"
crontab "$TEMP_CRON"
rm "$TEMP_CRON"

echo "✅ Cronjob added successfully!"
echo ""

# Verify installation
echo "════════════════════════════════════════════════════════════"
echo "✓ VERIFICATION"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "Current crontab entries:"
echo "────────────────────────"
crontab -l | grep -A 1 "fetch_agentic_ai_updates.py" || echo "   (No entries found)"

echo ""
echo "════════════════════════════════════════════════════════════"
echo "✅ SETUP COMPLETE!"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "📌 What's happening next:"
echo "   1. Script will run daily at 09:00"
echo "   2. Fetches top GitHub projects on Agentic AI"
echo "   3. Searches for YouTube videos"
echo "   4. Gets latest news from Hacker News"
echo "   5. Sends summary to Telegram"
echo ""
echo "📂 Logs saved to: $LOG_FILE"
echo ""
echo "🔧 To view logs:"
echo "   tail -f $LOG_FILE"
echo ""
echo "❌ To remove cronjob:"
echo "   crontab -e"
echo "   (Remove the line containing fetch_agentic_ai_updates.py)"
echo ""
echo "🧪 To test manually:"
echo "   $PYTHON_PATH $SCRIPT_PATH"
echo ""
