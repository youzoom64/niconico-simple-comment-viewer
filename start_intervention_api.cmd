@echo off
setlocal
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command "if (Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 8793 -State Listen -ErrorAction SilentlyContinue) { exit 0 } exit 1"
if "%ERRORLEVEL%"=="0" (
  echo [niconico-simple-comment-viewer] Intervention API already running on 127.0.0.1:8793
  endlocal & exit /b 0
)
set "PYTHON=%CD%\.venv\Scripts\python.exe"
if not exist "%PYTHON%" (
  echo ERROR: Local Python environment was not found. Run setup.cmd first.
  endlocal & exit /b 1
)
set "LOG_DIR=%CD%\data"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
set "LOG=%LOG_DIR%\intervention_api.log"
set "ERR=%LOG_DIR%\intervention_api.err.log"
start "Niconico Comment Viewer Intervention API" /b "%PYTHON%" main.py --entrypoint api --host 127.0.0.1 --port 8793 > "%LOG%" 2> "%ERR%"
endlocal
