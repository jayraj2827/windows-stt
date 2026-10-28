@echo off
setlocal
cd /d "%~dp0"
title Windows STT - Stop Subsystem

echo ==============================================================
echo   Windows STT Subsystem — Stopping
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

:: 3. Force terminate any lingering python.exe running app.main
powershell -NoProfile -Command "Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like '*app.main*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>&1

echo.
echo ==============================================================
echo   [SUCCESS] Windows STT Subsystem has been STOPPED.
echo ==============================================================
echo   All background voice recognition processes are terminated.
echo ==============================================================
echo.
echo Press any key to close this window . . .
pause >nul
exit /b 0
