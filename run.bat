@echo off
setlocal
cd /d "%~dp0"
title Friday STT - Launcher

echo ==============================================================
echo   Friday STT System — Starting
echo ==============================================================

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found at .venv\Scripts\python.exe.
    pause
    exit /b 1
)

:: Cleanly terminate any older instance first so latest code always loads
if exist ".stt.pid" (
    set /p OLD_PID=<.stt.pid
    if not "%OLD_PID%"=="" taskkill /F /PID %OLD_PID% >nul 2>&1
    del .stt.pid >nul 2>&1
)
taskkill /F /IM pythonw.exe >nul 2>&1
timeout /t 1 /nobreak >nul

:: Launch the fresh background subsystem via pythonw.exe
start "" ".venv\Scripts\pythonw.exe" -m app.main %*

:: Wait briefly for startup
timeout /t 2 /nobreak >nul

echo.
echo ==============================================================
echo   [SUCCESS] Friday STT System is RUNNING in background!
echo ==============================================================
echo    - Assistant:    Friday STT System
echo    - Acceleration: NVIDIA RTX 4060 GPU (CUDA Float16)
echo    - Push-to-Talk: Hold [Ctrl + Space], speak, release to paste
echo    - Hands-Free:   Press [Ctrl + Shift + Space] to toggle
echo    - System Tray:  Cyan microphone icon is active near your clock
echo    - To Stop:      Double-click stop.bat anytime
echo ==============================================================
echo.
echo Press any key to close this window . . .
pause >nul
exit /b 0
