@echo off
setlocal
chcp 65001 > nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
set "ROOT=%~dp0..\.."
set "NICONICO_ROOT=%~dp0.."
set "PYTHON_EXE="
set "PYTHONW_EXE="
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

if not defined PYTHON_EXE (
  echo ERROR: Niconico venv Python not found.
  echo Expected: %NICONICO_ROOT%\niconico-watch-app\.venv\Scripts\python.exe
  endlocal & exit /b 1
)

if /i "%~1"=="--wait" (
  shift /1
  call "J:\tools\scripts\rtfw_lan_client\start_service.cmd"
  if errorlevel 1 (
    echo ERROR: RTFW LAN Client could not be started.
    endlocal & exit /b 1
  )
  call "%~dp0start_intervention_api.cmd"
  "%PYTHON_EXE%" main.py --entrypoint gui %*
  set "EXIT_CODE=%ERRORLEVEL%"
  call "%~dp0stop_intervention_api.cmd"
  endlocal & exit /b %EXIT_CODE%
)

start "Niconico Simple Comment Viewer" /min cmd /c ""%~f0" --wait %*"
set "EXIT_CODE=%ERRORLEVEL%"
endlocal & exit /b %EXIT_CODE%
