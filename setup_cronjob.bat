@echo off
REM ════════════════════════════════════════════════════════════
REM SETUP CRONJOB OTOMATIS - AGENTIC AI & LLM UPDATES (WINDOWS)
REM Script ini mengatur Windows Task Scheduler untuk menjalankan
REM update Agentic AI & LLM setiap hari jam 09:00
REM ════════════════════════════════════════════════════════════

chcp 65001 > nul
setlocal enabledelayedexpansion

echo.
echo ════════════════════════════════════════════════════════════
echo 🤖 SETUP CRONJOB - AGENTIC AI LLM UPDATES (WINDOWS)
echo ════════════════════════════════════════════════════════════
echo.

REM Check Administrator Rights
whoami /priv | find "SeCreatePageFile" > nul
if errorlevel 1 (
    echo ❌ Error: This script requires Administrator privileges
    echo    Please run Command Prompt as Administrator and try again
    pause
    exit /b 1
)

echo ✅ Running with Administrator privileges
echo.

REM Get current directory
set SCRIPT_DIR=%~dp0
set SCRIPT_PATH=%SCRIPT_DIR%fetch_agentic_ai_updates.py
set LOG_FILE=%TEMP%\agentic_ai_updates.log

echo 📋 Configuration:
echo    Script Directory: %SCRIPT_DIR%
echo    Script Path: %SCRIPT_PATH%
echo    Log File: %LOG_FILE%
echo.

REM Check if Python script exists
if not exist "%SCRIPT_PATH%" (
    echo ❌ Error: fetch_agentic_ai_updates.py not found
    echo    Expected location: %SCRIPT_PATH%
    pause
    exit /b 1
)

echo ✅ Script found
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    py --version >nul 2>&1
    if errorlevel 1 (
        echo ❌ Error: Python not found
        echo    Please install Python 3 from https://www.python.org/
        pause
        exit /b 1
    )
    set PYTHON_CMD=py
) else (
    set PYTHON_CMD=python
)

echo ✅ Python found
echo.

REM Check for required Python packages
echo 📦 Checking Python packages...
%PYTHON_CMD% -m pip list | find "requests" >nul
if errorlevel 1 (
    echo    Installing requests...
    %PYTHON_CMD% -m pip install requests -q
    echo    ✅ requests installed
)

%PYTHON_CMD% -m pip list | find "python-dotenv" >nul
if errorlevel 1 (
    echo    Installing python-dotenv...
    %PYTHON_CMD% -m pip install python-dotenv -q
    echo    ✅ python-dotenv installed
)

echo ✅ All packages verified
echo.

REM Check for .env file
if not exist "%SCRIPT_DIR%.env" (
    echo ⚠️  .env file not found!
    echo    Create .env file with:
    echo    TELEGRAM_BOT_TOKEN=your_token_here
    echo    TELEGRAM_CHAT_ID=your_chat_id_here
    echo.
    set /p CREATE_ENV="Do you want to create .env now? (y/n): "
    if /i "!CREATE_ENV!"=="y" (
        set /p BOT_TOKEN="Enter TELEGRAM_BOT_TOKEN: "
        set /p CHAT_ID="Enter TELEGRAM_CHAT_ID: "
        (
            echo TELEGRAM_BOT_TOKEN=!BOT_TOKEN!
            echo TELEGRAM_CHAT_ID=!CHAT_ID!
        ) > "%SCRIPT_DIR%.env"
        echo ✅ .env file created
    )
) else (
    echo ✅ .env file found
)

echo.

REM Create Windows Task
echo ════════════════════════════════════════════════════════════
echo ⚙️  CREATING WINDOWS TASK
echo ════════════════════════════════════════════════════════════
echo.

set TASK_NAME=AgenticAI_LLM_Updates
set TASK_DESC=Daily Agentic AI & LLM Updates - Runs at 09:00

echo Task Name: %TASK_NAME%
echo Schedule: Every day at 09:00
echo Description: %TASK_DESC%
echo.

REM Check if task already exists
tasklist /FI "TASKNAME eq %TASK_NAME%" 2>NUL | find /I "%TASK_NAME%" >NUL
if "%ERRORLEVEL%"=="0" (
    echo ⚠️  Task already exists!
    set /p DELETE_TASK="Do you want to remove and recreate it? (y/n): "
    if /i "!DELETE_TASK!"=="y" (
        echo    Removing existing task...
        schtasks /delete /tn "%TASK_NAME%" /f >nul 2>&1
        echo    ✅ Task removed
    ) else (
        echo    Installation cancelled
        pause
        exit /b 0
    )
)

REM Get Python executable path
for /f "tokens=*" %%i in ('%PYTHON_CMD% -c "import sys; print(sys.executable)"') do set PYTHON_EXE=%%i

echo Creating scheduled task...
echo.

REM Create the task with proper escaping
schtasks /create /tn "%TASK_NAME%" /tr "%PYTHON_EXE% \"%SCRIPT_PATH%\" >> \"%LOG_FILE%\" 2^>^&1" /sc daily /st 09:00 /ru SYSTEM /f >nul 2>&1

if errorlevel 1 (
    echo ❌ Error creating task
    echo    Trying alternative method...
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
        "$action = New-ScheduledTaskAction -Execute '%PYTHON_EXE%' -Argument '\"%SCRIPT_PATH%\"'; ^
        $trigger = New-ScheduledTaskTrigger -Daily -At 09:00AM; ^
        Register-ScheduledTask -TaskName '%TASK_NAME%' -Action $action -Trigger $trigger -RunLevel Highest -Force" >nul 2>&1
    
    if errorlevel 1 (
        echo ❌ Failed to create task
        pause
        exit /b 1
    )
)

echo ✅ Task created successfully!
echo.

REM Verify installation
echo ════════════════════════════════════════════════════════════
echo ✓ VERIFICATION
echo ════════════════════════════════════════════════════════════
echo.

tasklist /FI "TASKNAME eq %TASK_NAME%" 2>NUL | find /I "%TASK_NAME%" >NUL
if "%ERRORLEVEL%"=="0" (
    echo ✅ Task successfully created and active!
    echo.
    schtasks /query /tn "%TASK_NAME%" /fo list /v
) else (
    echo ⚠️  Task not found
)

echo.
echo ════════════════════════════════════════════════════════════
echo ✅ SETUP COMPLETE!
echo ════════════════════════════════════════════════════════════
echo.
echo 📌 WHAT HAPPENS NEXT:
echo    1. Task will run daily at 09:00
echo    2. Fetches top GitHub projects on Agentic AI
echo    3. Searches for YouTube videos
echo    4. Gets latest news from Hacker News
echo    5. Sends summary to Telegram
echo.
echo 📂 Logs saved to: %LOG_FILE%
echo.
echo 🔧 TO MANAGE TASK:
echo    1. Open Task Scheduler:
echo       - Press Windows + R
echo       - Type: taskschd.msc
echo       - Press Enter
echo       - Find: %TASK_NAME%
echo.
echo    2. To run manually:
echo       schtasks /run /tn "%TASK_NAME%"
echo.
echo    3. To view logs:
echo       type "%LOG_FILE%"
echo.
echo    4. To delete task:
echo       schtasks /delete /tn "%TASK_NAME%" /f
echo.
echo 🧪 TO TEST SCRIPT MANUALLY:
echo    %PYTHON_EXE% "%SCRIPT_PATH%"
echo.

pause
