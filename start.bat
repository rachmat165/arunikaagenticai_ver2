@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
chcp 65001 >nul

REM Usage:
REM   start.bat           -> tampilkan menu
REM   start.bat 1         -> langsung start bot
REM   start.bat 2         -> update apps
REM   start.bat 0         -> keluar

if "%~1"=="" goto MENU
if "%~1"=="1" goto START_BOT
if "%~1"=="2" goto UPDATE_MAIN
if "%~1"=="0" goto EXIT

:MENU
cls
echo =========================================================
echo  REFLECTIVE KOALA ^| Dewi Bot ATG
echo =========================================================
echo  1. Start Bot Telegram
echo  2. Update Aplikasi (GitHub + Python packages)
echo  3. Setup Model AI
echo  4. Hapus lock file (jika bot stuck)
echo  5. Update Hermes Agent (cek release terbaru)
echo  0. Keluar
echo =========================================================
echo.
set /p CHOICE="Pilih menu [0-5]: "

if "%CHOICE%"=="1" goto START_BOT
if "%CHOICE%"=="2" goto UPDATE_MAIN
if "%CHOICE%"=="3" goto SETUP_MODEL
if "%CHOICE%"=="4" goto CLEAR_LOCK
if "%CHOICE%"=="5" goto UPDATE_HERMES
if "%CHOICE%"=="0" goto EXIT
echo [!] Pilihan tidak valid
timeout /t 1 >nul
goto MENU

:START_BOT
cls
echo =========================================================
echo  [INFO] Memulai Dewi Bot Telegram
echo =========================================================
echo.

REM --- Cek lock file ---
call :CHECK_LOCK
if "!LOCK_CONFLICT!"=="1" (
  echo.
  pause
  goto MENU
)

REM --- Cari Python ---
call :FIND_PYTHON
if "!PYTHON_EXE!"=="" (
  echo [ERROR] Python 3.11 tidak ditemukan.
  echo         Install Python 3.11 dari https://www.python.org/downloads/
  echo         Pastikan opsi "Add Python to PATH" dicentang saat install.
  echo.
  pause
  goto MENU
)
echo [OK] Python: !PYTHON_EXE!

REM --- Siapkan venv ---
call :ENSURE_VENV
echo [OK] Venv : %~dp0.venv311\Scripts\python.exe
echo.
echo [INFO] Bot berjalan... Tekan Ctrl+C untuk menghentikan.
echo =========================================================
echo.

"%~dp0.venv311\Scripts\python.exe" run.py
set "EXIT_CODE=!ERRORLEVEL!"

echo.
echo =========================================================
if "!EXIT_CODE!"=="0" (
  echo [INFO] Bot berhenti normal (exit code 0).
) else (
  echo [ERROR] Bot berhenti dengan exit code !EXIT_CODE!
  echo         Lihat pesan error di atas untuk detail.
)
echo =========================================================
echo.
pause
goto MENU

:CHECK_LOCK
set "LOCK_CONFLICT=0"
set "LOCK_FILE=%~dp0data\telegram_bot.lock"
if not exist "!LOCK_FILE!" exit /b 0

REM Baca PID dari lock file
set "LOCK_PID="
for /f "usebackq delims=" %%P in ("!LOCK_FILE!") do (
  if "!LOCK_PID!"=="" set "LOCK_PID=%%P"
)

if "!LOCK_PID!"=="" (
  echo [INFO] Lock file kosong/rusak, menghapus...
  del "!LOCK_FILE!" >nul 2>&1
  exit /b 0
)

REM Cek apakah PID masih aktif
tasklist /FI "PID eq !LOCK_PID!" /FO CSV /NH 2>nul | find "!LOCK_PID!" >nul 2>&1
if errorlevel 1 (
  echo [INFO] Lock stale ditemukan (PID !LOCK_PID! tidak aktif). Menghapus otomatis...
  del "!LOCK_FILE!" >nul 2>&1
  exit /b 0
)

echo [WARN] Bot Telegram sudah berjalan (PID !LOCK_PID!).
echo        Hentikan proses tersebut dulu, atau pilih menu [4] untuk paksa hapus lock.
set "LOCK_CONFLICT=1"
exit /b 0

:CLEAR_LOCK
cls
echo =========================================================
echo  [INFO] Hapus Lock File
echo =========================================================
echo.
if exist "%~dp0data\telegram_bot.lock" (
  del "%~dp0data\telegram_bot.lock" >nul 2>&1
  echo [OK] Lock file dihapus. Sekarang bisa start bot kembali.
) else (
  echo [INFO] Tidak ada lock file yang perlu dihapus.
)
echo.
pause
goto MENU

:UPDATE_MAIN
cls
echo =========================================================
echo  [INFO] Update Aplikasi
echo =========================================================
echo.
echo Pilih jenis update:
echo  A. Update dari GitHub (kode terbaru)
echo  B. Update Python packages (requirements.txt)
echo  C. Update semua (GitHub + packages)
echo  D. Install ulang dependencies (jika ada error)
echo  0. Kembali
echo.
set /p UPD_CHOICE="Pilih [A/B/C/D/0]: "

if /i "%UPD_CHOICE%"=="A" goto UPDATE_GIT
if /i "%UPD_CHOICE%"=="B" goto UPDATE_PIP
if /i "%UPD_CHOICE%"=="C" goto UPDATE_ALL
if /i "%UPD_CHOICE%"=="D" goto REINSTALL
if "%UPD_CHOICE%"=="0" goto MENU
goto UPDATE_MAIN

:UPDATE_GIT
echo.
echo [GIT] Pull origin master...
git pull origin master
if errorlevel 1 (
  echo [WARN] Git pull gagal. Cek git dan koneksi internet.
)
pause
goto MENU

:UPDATE_PIP
echo.
call :FIND_PYTHON
call :ENSURE_VENV
echo [PIP] Upgrade pip dan install requirements...
"%~dp0.venv311\Scripts\python.exe" -m pip install --upgrade pip --quiet
"%~dp0.venv311\Scripts\python.exe" -m pip install -r "%~dp0requirements.txt" --upgrade --quiet
echo [OK] Update packages selesai.
pause
goto MENU

:UPDATE_ALL
call :UPDATE_GIT
call :UPDATE_PIP
goto MENU

:REINSTALL
echo.
echo [SETUP] Install ulang .venv311...
if exist "%~dp0.venv311" rmdir /s /q "%~dp0.venv311"
call :FIND_PYTHON
call :ENSURE_VENV
echo [OK] Install ulang selesai.
pause
goto MENU

:SETUP_MODEL
cls
echo =========================================================
echo  Setup Model AI
echo =========================================================
echo.
echo Gunakan perintah /settings di Telegram untuk memilih model AI.
echo.
pause
goto MENU

:UPDATE_HERMES
cls
echo =========================================================
echo  [INFO] Update Hermes Agent
echo  Sumber: github.com/NousResearch/hermes-agent
echo =========================================================
echo.

REM --- Pastikan Python & venv tersedia ---
call :FIND_PYTHON
if "!PYTHON_EXE!"=="" (
  echo [ERROR] Python tidak ditemukan. Jalankan menu 2 terlebih dahulu.
  pause
  goto MENU
)
call :ENSURE_VENV

REM --- Cek koneksi internet ---
echo [INFO] Memeriksa koneksi internet...
ping -n 1 api.github.com >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Tidak dapat terhubung ke api.github.com
  echo         Periksa koneksi internet Anda.
  pause
  goto MENU
)
echo [OK] Koneksi internet tersedia.
echo.

REM --- Jalankan update script ---
"%~dp0.venv311\Scripts\python.exe" "%~dp0scripts\update_hermes.py"

goto MENU

REM ==========================
REM Subroutines
REM ==========================

:FIND_PYTHON
set "PYTHON_EXE="
if exist "C:\Program Files\Python311\python.exe" (
  set "PYTHON_EXE=C:\Program Files\Python311\python.exe"
  exit /b 0
)
if exist "C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python311\python.exe" (
  set "PYTHON_EXE=C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python311\python.exe"
  exit /b 0
)
REM Fallback: python di PATH
for /f "usebackq delims=" %%P in (`where python 2^>nul`) do (
  if "!PYTHON_EXE!"=="" set "PYTHON_EXE=%%P"
)
exit /b 0

:ENSURE_VENV
if exist "%~dp0.venv311\Scripts\python.exe" exit /b 0

echo [SETUP] Membuat virtual environment (.venv311)...
"!PYTHON_EXE!" -m venv "%~dp0.venv311"
if errorlevel 1 (
  echo [ERROR] Gagal membuat venv. Cek apakah Python 3.11 terinstall dengan benar.
  pause
  goto MENU
)
echo [SETUP] Install dependencies dari requirements.txt...
"%~dp0.venv311\Scripts\python.exe" -m pip install --upgrade pip --quiet
"%~dp0.venv311\Scripts\python.exe" -m pip install -r "%~dp0requirements.txt" --quiet
echo [OK] Dependencies terinstall.
exit /b 0

:EXIT
echo.
echo Sampai jumpa!
timeout /t 1 >nul
exit /b 0
