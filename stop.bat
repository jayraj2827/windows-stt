@echo off
setlocal
cd /d "%~dp0"

echo ========================================================
echo  Stopping Windows STT Subsystem
echo ========================================================

set STOPPED=0

:: Check PID file first
if exist ".stt.pid" (
    set /p PID=<.stt.pid
    if not "%PID%"=="" (
        taskkill /F /PID %PID% >nul 2>&1
        if %ERRORLEVEL% equ 0 (
            echo Stopped Windows STT process (PID %PID%).
            set STOPPED=1
        )
    )
    del .stt.pid >nul 2>&1
)

:: Terminate any python processes running out of our local .venv directory
for /f "tokens=2" %%A in ('tasklist /nh /fi "imagename eq pythonw.exe" 2^>nul') do (
    wmic process where "ProcessId=%%A and ExecutablePath like '%%STT\\.venv%%'" call terminate >nul 2>&1
    if %ERRORLEVEL% equ 0 set STOPPED=1
)

for /f "tokens=2" %%A in ('tasklist /nh /fi "imagename eq python.exe" 2^>nul') do (
    wmic process where "ProcessId=%%A and ExecutablePath like '%%STT\\.venv%%'" call terminate >nul 2>&1
    if %ERRORLEVEL% equ 0 set STOPPED=1
)

echo.
echo [OK] Windows STT Subsystem is stopped.
timeout /t 2 >nul
exit /b 0

