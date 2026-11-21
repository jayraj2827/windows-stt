@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
title Friday Web Studio — Launcher

echo ==============================================================
echo   Friday Web Studio — Local AI Studio
echo ==============================================================
echo    - Acceleration: NVIDIA RTX 4060 GPU (CUDA float16)
echo    - URL:          http://127.0.0.1:8765
echo ==============================================================

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found at .venv\Scripts\python.exe.
    pause
    exit /b 1
)

:: 1. Check if port 8765 is already listening (hosted by Desktop Assistant or existing studio)
netstat -ano | findstr :8765 | findstr LISTENING >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    echo ==============================================================
    echo [CHECKPOINT] Web Studio is ALREADY ACTIVE and sharing the GPU model!
    echo Opening http://127.0.0.1:8765 in your default browser...
    echo ==============================================================
    start http://127.0.0.1:8765
    exit /b 0
)

:: 2. If Desktop Assistant (pythonw.exe) is running, wait briefly for it to finish warming up and bind port 8765
tasklist /FI "IMAGENAME eq pythonw.exe" 2>nul | findstr /I "pythonw.exe" >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    echo [INFO] Desktop Assistant is currently active and loading the model in memory...
    echo Waiting for Web Studio endpoint to attach...
    for /L %%i in (1,1,10) do (
        netstat -ano | findstr :8765 | findstr LISTENING >nul 2>&1
        if !ERRORLEVEL! EQU 0 (
            echo ==============================================================
            echo [CHECKPOINT] Successfully attached to shared GPU model!
            echo Opening http://127.0.0.1:8765 in your browser...
            echo ==============================================================
            start http://127.0.0.1:8765
            exit /b 0
        )
        ping 127.0.0.1 -n 2 >nul
    )
)

:: 3. Otherwise, launch standalone FastAPI Web Studio server
echo Starting standalone Web Studio server on port 8765...
"%~dp0.venv\Scripts\python.exe" -m app.web.server

echo.
echo Press any key to close this window . . .
pause >nul
exit /b 0
