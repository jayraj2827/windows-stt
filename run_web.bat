@echo off
setlocal
cd /d "%~dp0"
title Friday Web Studio — Launcher

echo ==============================================================
echo   Friday Web Studio — Starting Local Server
echo ==============================================================
echo    - Acceleration: NVIDIA RTX 4060 GPU (CUDA float16)
echo    - URL:          http://127.0.0.1:8765
echo    - Tasks:        Audio-to-Text Transcription ^& Translation
echo ==============================================================

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found at .venv\Scripts\python.exe.
    pause
    exit /b 1
)

:: Cleanly terminate any previously running web server on port 8765
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8765 ^| findstr LISTENING') do (
    taskkill /F /PID %%a >nul 2>&1
)

:: Launch Web Studio server
echo Starting Web Studio server and opening your browser...
"%~dp0.venv\Scripts\python.exe" -m app.web.server

echo.
echo Press any key to close this window . . .
pause >nul
exit /b 0
