@echo off
setlocal
cd /d "%~dp0"
echo Starting Antigravity STT in Debug / Console mode...
".venv\Scripts\python.exe" -m app.main --settings
pause

