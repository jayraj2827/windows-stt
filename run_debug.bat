@echo off
setlocal
cd /d "%~dp0"
title Friday STT - Console Debug Mode

echo ==============================================================
echo   Friday STT System — Starting in Debug Mode
echo ==============================================================

:: Cleanly stop any existing background instance first so latest code is loaded
if exist ".stt.pid" (
    set /p OLD_PID=<.stt.pid
    if not "%OLD_PID%"=="" taskkill /F /PID %OLD_PID% >nul 2>&1
    del .stt.pid >nul 2>&1
)
taskkill /F /IM pythonw.exe >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Windows STT*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Antigravity STT*" >nul 2>&1
timeout /t 1 /nobreak >nul

echo.
echo ==============================================================
echo   [RUNNING] Friday STT System — Console Debug Mode
echo ==============================================================
echo    - Assistant: Friday STT System
echo    - GPU: NVIDIA RTX 4060 (CUDA Float16)
echo    - Real-time Faster-Whisper logs and events will appear below.
echo    - The Control Hub will open automatically.
echo    - To Stop: Close this window or press Ctrl+C.
echo ==============================================================
echo.

".venv\Scripts\python.exe" -m app.main --settings

echo.
echo ==============================================================
echo   [STOPPED] Friday STT Debug session has ended.
echo ==============================================================
echo.
echo Press any key to close this window . . .
pause >nul
exit /b 0
