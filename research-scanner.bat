@echo off
setlocal ENABLEDELAYEDEXPANSION

REM — Root to this script
set ROOT=%~dp0
cd /d "%ROOT%"

REM — Ensure output dir exists
if not exist output mkdir output

REM — Ensure venv exists and deps installed
if not exist .venv (
  echo [setup] creating venv...
  py -3 -m venv .venv || python -m venv .venv
)
call .venv\Scripts\activate.bat

pip show -q openai >NUL 2>&1
if errorlevel 1 (
  echo [setup] installing requirements...
  pip install -r requirements.txt --upgrade
)

REM — Launch the PowerShell GUI
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\gui.ps1" -WorkingDir "%ROOT%"
endlocal
