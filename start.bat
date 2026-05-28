@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
title REFLECTIVE KOALA — Dewi Bot ATG

:MENU
cls
echo.
echo  ╔══════════════════════════════════════════════════════╗
echo  ║       REFLECTIVE KOALA  ^|  Dewi Bot ATG             ║
echo  ║       PT. Arunika Teknologi Global                   ║
echo  ╠══════════════════════════════════════════════════════╣
echo  ║                                                      ║
echo  ║   1. Start Bot Telegram                              ║
echo  ║   2. Update Aplikasi  (GitHub + Python packages)     ║
echo  ║   3. Setup Model AI   (Anthropic / OpenRouter /      ║
echo  ║                        LM Studio Lokal)              ║
echo  ║   0. Keluar                                          ║
echo  ║                                                      ║
echo  ╚══════════════════════════════════════════════════════╝
echo.

set /p CHOICE="  Pilih menu [0-3]: "

if "%CHOICE%"=="1" goto START_BOT
if "%CHOICE%"=="2" goto UPDATE
if "%CHOICE%"=="3" goto SETUP_MODEL
if "%CHOICE%"=="0" goto EXIT
echo  [!] Pilihan tidak valid. Coba lagi.
timeout /t 1 >nul
goto MENU

REM ═══════════════════════════════════════════════════════════
:START_BOT
cls
echo  ╔══════════════════════════════════════════════════════╗
echo  ║   1. Start Bot Telegram                              ║
echo  ╚══════════════════════════════════════════════════════╝
echo.

call :FIND_PYTHON
if "%PYTHON_EXE%"=="" (
    echo  [ERROR] Python tidak ditemukan!
    echo  Jalankan menu 2 (Update) terlebih dahulu.
    pause
    goto MENU
)

call :ENSURE_VENV

echo  [INFO] Menjalankan Dewi Bot...
echo  [INFO] Tekan Ctrl+C untuk menghentikan
echo  ──────────────────────────────────────────────────────
echo.
"%VENV_PYTHON%" run.py
echo.
echo  [INFO] Bot berhenti.
pause
goto MENU

REM ═══════════════════════════════════════════════════════════
:UPDATE
cls
echo  ╔══════════════════════════════════════════════════════╗
echo  ║   2. Update Aplikasi                                 ║
echo  ╚══════════════════════════════════════════════════════╝
echo.
echo  Pilih jenis update:
echo.
echo    A. Update dari GitHub (kode terbaru)
echo    B. Update Python packages (requirements.txt)
echo    C. Update semua (GitHub + packages)
echo    D. Install ulang dependencies (jika ada error)
echo    0. Kembali
echo.
set /p UPD_CHOICE="  Pilih [A/B/C/D/0]: "

if /i "%UPD_CHOICE%"=="A" goto UPDATE_GIT
if /i "%UPD_CHOICE%"=="B" goto UPDATE_PIP
if /i "%UPD_CHOICE%"=="C" goto UPDATE_ALL
if /i "%UPD_CHOICE%"=="D" goto REINSTALL
if "%UPD_CHOICE%"=="0" goto MENU
goto UPDATE

:UPDATE_GIT
echo.
echo  [GIT] Mengambil update dari GitHub...
git pull origin master
if errorlevel 1 (
    echo  [WARN] Git pull gagal. Pastikan git terinstall dan koneksi internet tersedia.
)
echo.
echo  [OK] Kode berhasil diupdate.
pause
goto MENU

:UPDATE_PIP
echo.
call :FIND_PYTHON
call :ENSURE_VENV
echo  [PIP] Mengupdate Python packages...
"%VENV_PYTHON%" -m pip install --upgrade pip --quiet
"%VENV_PYTHON%" -m pip install -r requirements.txt --upgrade --quiet
echo  [OK] Packages berhasil diupdate.
pause
goto MENU

:UPDATE_ALL
call :UPDATE_GIT
call :UPDATE_PIP
goto MENU

:REINSTALL
echo.
echo  [SETUP] Menghapus venv lama dan install ulang...
if exist venv rmdir /s /q venv
call :FIND_PYTHON
call :ENSURE_VENV
echo  [OK] Install ulang selesai.
pause
goto MENU

REM ═══════════════════════════════════════════════════════════
:SETUP_MODEL
cls
echo  ╔══════════════════════════════════════════════════════╗
echo  ║   3. Setup Model AI                                  ║
echo  ╚══════════════════════════════════════════════════════╝
echo.
echo  Pilih provider model:
echo.
echo    1. Anthropic Claude  (gunakan API key)
echo    2. OpenRouter        (100+ model via API key)
echo    3. LM Studio Lokal   (model offline di PC ini)
echo    4. Lihat konfigurasi .env saat ini
echo    0. Kembali
echo.
set /p MDL_CHOICE="  Pilih [1-4/0]: "

if "%MDL_CHOICE%"=="1" goto SETUP_ANTHROPIC
if "%MDL_CHOICE%"=="2" goto SETUP_OPENROUTER
if "%MDL_CHOICE%"=="3" goto SETUP_LMSTUDIO
if "%MDL_CHOICE%"=="4" goto SHOW_ENV
if "%MDL_CHOICE%"=="0" goto MENU
goto SETUP_MODEL

:SETUP_ANTHROPIC
echo.
echo  ── Anthropic Claude ──────────────────────────────────
echo  Dapatkan API key di: https://console.anthropic.com
echo.
set /p ANT_KEY="  Masukkan ANTHROPIC_API_KEY (kosongkan = skip): "
if not "%ANT_KEY%"=="" (
    call :SET_ENV ANTHROPIC_API_KEY "%ANT_KEY%"
    echo  [OK] ANTHROPIC_API_KEY tersimpan.
)
pause
goto SETUP_MODEL

:SETUP_OPENROUTER
echo.
echo  ── OpenRouter ─────────────────────────────────────────
echo  Dapatkan API key di: https://openrouter.ai/keys
echo.
set /p OR_KEY="  Masukkan OPENROUTER_API_KEY (kosongkan = skip): "
if not "%OR_KEY%"=="" (
    call :SET_ENV OPENROUTER_API_KEY "%OR_KEY%"
    echo  [OK] OPENROUTER_API_KEY tersimpan.
)
pause
goto SETUP_MODEL

:SETUP_LMSTUDIO
echo.
echo  ── LM Studio (Model Lokal) ────────────────────────────
echo.
echo  Langkah setup LM Studio:
echo  1. Download LM Studio dari: https://lmstudio.ai
echo  2. Install dan buka LM Studio
echo  3. Download model pilihan Anda (Qwen, Llama, Mistral, dll)
echo  4. Klik tab "Local Server" ^> Start Server
echo  5. Server berjalan di: http://localhost:1234
echo.

REM Cek apakah LM Studio sudah berjalan
curl -s http://localhost:1234/v1/models >nul 2>&1
if errorlevel 1 (
    echo  [!] LM Studio server belum berjalan di localhost:1234
    echo  Pastikan LM Studio sudah distart sebelum menggunakan
    echo  fitur ini di bot Telegram.
) else (
    echo  [OK] LM Studio terdeteksi di localhost:1234!
    echo  Model yang tersedia:
    curl -s http://localhost:1234/v1/models
)

echo.
set /p LMS_URL="  LM Studio URL [default: http://localhost:1234]: "
if "%LMS_URL%"=="" set LMS_URL=http://localhost:1234
call :SET_ENV LMSTUDIO_BASE_URL "%LMS_URL%"
echo  [OK] LMSTUDIO_BASE_URL=%LMS_URL% tersimpan.
echo.
echo  Di bot Telegram, gunakan /settings dan pilih
echo  provider "LM Studio" untuk menggunakan model lokal.
pause
goto SETUP_MODEL

:SHOW_ENV
echo.
echo  ── Konfigurasi .env saat ini ──────────────────────────
echo.
for /f "tokens=1,* delims==" %%A in (.env) do (
    set KEY=%%A
    set VAL=%%B
    REM Sembunyikan sebagian API key
    if "!KEY!"=="ANTHROPIC_API_KEY" (
        set SHORT=!VAL:~0,12!
        echo    ANTHROPIC_API_KEY=!SHORT!...
    ) else if "!KEY!"=="FIRECRAWL_API_KEY" (
        set SHORT=!VAL:~0,8!
        echo    FIRECRAWL_API_KEY=!SHORT!...
    ) else if "!KEY!"=="OPENROUTER_API_KEY" (
        if not "!VAL!"=="" (
            set SHORT=!VAL:~0,8!
            echo    OPENROUTER_API_KEY=!SHORT!...
        ) else (
            echo    OPENROUTER_API_KEY=[belum diset]
        )
    ) else (
        echo    %%A=%%B
    )
)
echo.
pause
goto SETUP_MODEL

REM ═══════════════════════════════════════════════════════════
REM Subroutines

:FIND_PYTHON
set PYTHON_EXE=
REM 1. Python bundled di folder project (portable)
if exist "%~dp0python\python.exe" (
    set PYTHON_EXE=%~dp0python\python.exe
    echo  [INFO] Menggunakan Python bundled: %~dp0python\python.exe
    goto :EOF
)
REM 2. Python di sistem
python --version >nul 2>&1
if not errorlevel 1 (
    for /f "delims=" %%P in ('where python') do (
        set PYTHON_EXE=%%P
        goto :FOUND_SYS_PYTHON
    )
    :FOUND_SYS_PYTHON
    echo  [INFO] Menggunakan Python sistem: !PYTHON_EXE!
    goto :EOF
)
echo  [ERROR] Python tidak ditemukan!
goto :EOF

:ENSURE_VENV
set VENV_PYTHON=%~dp0venv\Scripts\python.exe
if not exist "%VENV_PYTHON%" (
    echo  [SETUP] Membuat virtual environment...
    "%PYTHON_EXE%" -m venv "%~dp0venv"
    echo  [SETUP] Menginstall dependencies...
    "%VENV_PYTHON%" -m pip install --upgrade pip --quiet
    "%VENV_PYTHON%" -m pip install -r "%~dp0requirements.txt" --quiet
    echo  [SETUP] Selesai!
)
goto :EOF

:SET_ENV
REM Usage: call :SET_ENV KEY VALUE
REM Update or add a key in .env file
set ENV_KEY=%~1
set ENV_VAL=%~2
set ENV_FILE=%~dp0.env
set FOUND=0
set TEMPFILE=%TEMP%\env_temp.txt
if exist "%TEMPFILE%" del "%TEMPFILE%"
for /f "usebackq delims=" %%L in ("%ENV_FILE%") do (
    set LINE=%%L
    for /f "tokens=1 delims==" %%K in ("%%L") do (
        if "%%K"=="%ENV_KEY%" (
            echo %ENV_KEY%=%ENV_VAL%>>"%TEMPFILE%"
            set FOUND=1
        ) else (
            echo %%L>>"%TEMPFILE%"
        )
    )
)
if "%FOUND%"=="0" echo %ENV_KEY%=%ENV_VAL%>>"%TEMPFILE%"
copy /y "%TEMPFILE%" "%ENV_FILE%" >nul
del "%TEMPFILE%"
goto :EOF

:EXIT
echo.
echo  Sampai jumpa! 👋
timeout /t 1 >nul
exit /b 0
