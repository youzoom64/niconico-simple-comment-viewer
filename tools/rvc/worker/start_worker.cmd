@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
set "PYTHON=%~dp0.venv\Scripts\python.exe"
if not exist "%PYTHON%" set "PYTHON=%~dp0..\..\..\.venv\Scripts\python.exe"
if not exist "%PYTHON%" (
  echo ERROR: Python environment was not found. Run setup_worker.cmd first.
  endlocal & exit /b 1
)
if not exist ".env" (
  echo ERROR: Copy env.example to .env and configure the token and MMVC URL.
  endlocal & exit /b 1
)
"%PYTHON%" run_worker.py
endlocal & exit /b %ERRORLEVEL%
