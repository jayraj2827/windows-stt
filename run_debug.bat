@echo off
setlocal
cd /d "%~dp0"
title Windows STT - Console Debug Mode
echo Starting Windows STT in Debug / Console mode...
".venv\Scripts\python.exe" -m app.main --settings
pause

