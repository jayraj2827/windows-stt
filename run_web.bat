@echo off
setlocal
cd /d "%~dp0"
title Friday Web Studio — Launcher

echo ==============================================================
echo   Friday Web Studio — FastAPI Local Studio
echo ==============================================================
echo    - Acceleration: NVIDIA RTX 4060 GPU (CUDA float16)
echo    - URL:          http://127.0.0.1:8765
echo ==============================================================

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found at .venv\Scripts\python.exe.
    pause
    exit /b 1
)

:: Check if port 8765 is already active (hosted by Desktop Assistant or existing studio)
powershell -Command "$client = New-Object System.Net.Sockets.TcpClient; try { $client.Connect('127.0.0.1', 8765); exit 0 } catch { exit 1 }" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [CHECKPOINT] Model is already loaded and active in memory!
    echo Opening http://127.0.0.1:8765 in your browser...
    start http://127.0.0.1:8765
    exit /b 0
)

:: Otherwise, launch standalone FastAPI Web Studio server
echo Starting standalone Web Studio server and opening your browser...
"%~dp0.venv\Scripts\python.exe" -m app.web.server

echo.
echo Press any key to close this window . . .
pause >nul
exit /b 0
