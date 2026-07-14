@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 > nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"

if not exist "%PYTHON_EXE%" (
  echo ERROR: Local Python environment was not found.
  echo Run setup.cmd first.
  endlocal & exit /b 1
)

if /i "%~1"=="--wait" (
  shift /1
  call "%~dp0start_intervention_api.cmd"
  "%PYTHON_EXE%" main.py --entrypoint gui %*
  set "EXIT_CODE=!ERRORLEVEL!"
  call "%~dp0stop_intervention_api.cmd"
  for %%E in (!EXIT_CODE!) do endlocal & exit /b %%E
)

start "Niconico Simple Comment Viewer" /min cmd /c ""%~f0" --wait %*"
set "EXIT_CODE=%ERRORLEVEL%"
endlocal & exit /b %EXIT_CODE%
