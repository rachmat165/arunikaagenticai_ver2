@echo off
cd /d "%~dp0"
title REFLECTIVE KOALA — Dewi Bot ATG

echo.
echo  ╔══════════════════════════════════════╗
echo  ║   REFLECTIVE KOALA — Dewi Bot ATG   ║
echo  ║   PT. Arunika Teknologi Global       ║
echo  ╚══════════════════════════════════════╝
echo.

REM ── Check Python ─────────────────────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python tidak ditemukan!
    echo Silakan install Python 3.10+ dari https://python.org
    pause
    exit /b 1
)

REM ── Create venv if not exists ─────────────────────────────────────────────
if not exist "venv\Scripts\python.exe" (
    echo [SETUP] Membuat virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Gagal membuat venv!
        pause
        exit /b 1
    )
    echo [SETUP] Menginstall dependencies...
    venv\Scripts\pip install --upgrade pip --quiet
    venv\Scripts\pip install -r requirements.txt --quiet
    if errorlevel 1 (
        echo [ERROR] Gagal install requirements!
        pause
        exit /b 1
    )
    echo [SETUP] Setup selesai!
    echo.
)

REM ── Create required directories ───────────────────────────────────────────
if not exist "data" mkdir data
if not exist "output\surat" mkdir output\surat
if not exist "output\presentasi" mkdir output\presentasi
if not exist "output\sosmed" mkdir output\sosmed
if not exist "output\rnd" mkdir output\rnd
if not exist "output\logs" mkdir output\logs

REM ── Run bot ───────────────────────────────────────────────────────────────
echo [INFO] Menjalankan bot...
echo [INFO] Tekan Ctrl+C untuk menghentikan bot
echo.
venv\Scripts\python.exe run.py

echo.
echo [INFO] Bot berhenti.
pause
