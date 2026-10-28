@echo off
setlocal
cd /d "%~dp0"
title Friday STT - Stop System

echo ==============================================================
echo   Friday STT System — Stopping
echo ==============================================================

:: 1. Terminate PID from .stt.pid if present
if exist ".stt.pid" (
    set /p PID=<.stt.pid
    if not "%PID%"=="" (
        taskkill /F /PID %PID% >nul 2>&1
    )
    del .stt.pid >nul 2>&1
)

:: 2. Force terminate any background pythonw.exe
taskkill /F /IM pythonw.exe >nul 2>&1

:: 3. Terminate any window matching Friday STT, Windows STT, or Antigravity
taskkill /F /FI "WINDOWTITLE eq Friday STT*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Windows STT*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Antigravity STT*" >nul 2>&1

:: 4. Force terminate any lingering python.exe running app.main
powershell -NoProfile -Command "Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like '*app.main*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>&1

echo.
echo ==============================================================
echo   [SUCCESS] Friday STT System has been STOPPED.
echo ==============================================================
echo   All Friday STT background processes are terminated.
echo ==============================================================
echo.
echo Press any key to close this window . . .
pause >nul
exit /b 0
