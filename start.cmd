@echo off
setlocal
chcp 65001 > nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
set "ROOT=%~dp0..\.."
set "NICONICO_ROOT=%~dp0.."
set "PYTHON_EXE=python"
set "PYTHONW_EXE=pythonw"
if exist "%~dp0.venv\Scripts\pythonw.exe" (
  set "PYTHONW_EXE=%~dp0.venv\Scripts\pythonw.exe"
  set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
) else if exist "%NICONICO_ROOT%\niconico-watch-app\.venv\Scripts\pythonw.exe" (
  set "PYTHONW_EXE=%NICONICO_ROOT%\niconico-watch-app\.venv\Scripts\pythonw.exe"
  set "PYTHON_EXE=%NICONICO_ROOT%\niconico-watch-app\.venv\Scripts\python.exe"
) else if exist "%ROOT%\.venv\Scripts\pythonw.exe" (
  set "PYTHONW_EXE=%ROOT%\.venv\Scripts\pythonw.exe"
  set "PYTHON_EXE=%ROOT%\.venv\Scripts\python.exe"
)

if /i "%~1"=="--wait" (
  shift /1
  "%PYTHON_EXE%" main.py --entrypoint gui %*
  set "EXIT_CODE=%ERRORLEVEL%"
  endlocal & exit /b %EXIT_CODE%
)

start "" "%PYTHONW_EXE%" "%~dp0main.py" --entrypoint gui %*
set "EXIT_CODE=%ERRORLEVEL%"
endlocal & exit /b %EXIT_CODE%
