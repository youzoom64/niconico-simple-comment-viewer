@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  if defined PYTHON_EXE (
    "%PYTHON_EXE%" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"
    if errorlevel 1 (
      echo ERROR: PYTHON_EXE must point to Python 3.11 or newer.
      endlocal & exit /b 1
    )
    "%PYTHON_EXE%" -m venv .venv
  ) else (
    where py >nul 2>nul
    if not errorlevel 1 (
      py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"
      if errorlevel 1 (
        echo ERROR: Python 3.11 or newer is required.
        endlocal & exit /b 1
      )
      py -3 -m venv .venv
    ) else (
      where python >nul 2>nul
      if errorlevel 1 (
        echo ERROR: Python was not found. Install Python 3.11 or set PYTHON_EXE.
        endlocal & exit /b 1
      )
      python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"
      if errorlevel 1 (
        echo ERROR: Python 3.11 or newer is required.
        endlocal & exit /b 1
      )
      python -m venv .venv
    )
  )
  if errorlevel 1 (
    echo ERROR: Failed to create .venv with Python 3.11.
    endlocal & exit /b 1
  )
)

".venv\Scripts\python.exe" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"
if errorlevel 1 (
  echo ERROR: Existing .venv is older than Python 3.11. Remove .venv and run setup.cmd again.
  endlocal & exit /b 1
)

".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 (
  endlocal & exit /b 1
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  endlocal & exit /b 1
)

echo Setup complete. Run start.cmd.
endlocal
