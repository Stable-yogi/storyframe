@echo off
cd /d "%~dp0"
if not exist config.json (
  echo config.json not found.
  echo Copy config.example.json to config.json and edit it first.
  pause
  exit /b
)
start "" "http://127.0.0.1:8000"
python app.py
pause
