@echo off
setlocal
cd /d "%~dp0"
title Windows STT - Console Debug Mode

echo ==============================================================
echo   [RUNNING] Windows STT Subsystem — Console Debug Mode
echo ==============================================================
echo    - GPU: NVIDIA RTX 4060 (CUDA Float16)
echo    - Real-time Faster-Whisper logs and events will appear below.
echo    - The Control Hub will open automatically.
echo    - To Stop: Close this window or press Ctrl+C.
echo ==============================================================
echo.

".venv\Scripts\python.exe" -m app.main --settings

echo.
echo ==============================================================
echo   [STOPPED] Windows STT Debug session has ended.
echo ==============================================================
echo.
echo Press any key to close this window . . .
pause >nul
exit /b 0
