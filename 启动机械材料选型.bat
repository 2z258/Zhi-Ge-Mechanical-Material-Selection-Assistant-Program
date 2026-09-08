@echo off
cd /d "%~dp0"
set "PYTHON=%LocalAppData%\Python\bin\python.exe"
if not exist "%PYTHON%" set "PYTHON=python.exe"
"%PYTHON%" -c "from pathlib import Path; from desktop_ui_v2 import launch; root=Path.cwd(); launch(root/'data'/'materials.db',root/'rules'/'weights.json')"
if errorlevel 1 (
  echo Desktop UI failed with exit code %errorlevel%.
  pause
)
