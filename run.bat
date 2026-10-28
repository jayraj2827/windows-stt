@echo off
setlocal
cd /d "%~dp0"

echo ========================================================
echo  Antigravity Voice Typing Subsystem (Faster-Whisper CUDA)
echo ========================================================

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found. Please install dependencies first.
    pause
    exit /b 1
)

:: Launch via python.exe so console logs are visible if launched directly,
:: or pass --settings to open the Control Hub immediately.
if "%1"=="--settings" (
    start "" ".venv\Scripts\python.exe" -m app.main --settings
) else if "%1"=="--silent" (
    start "" ".venv\Scripts\pythonw.exe" -m app.main
) else (
    echo Starting subsystem in background... (Access via System Tray or Hotkeys)
    start "" ".venv\Scripts\pythonw.exe" -m app.main
)

exit /b 0

