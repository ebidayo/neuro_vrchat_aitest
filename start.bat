@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

REM Move to repo root
cd /d "%~dp0"

echo === Misora_ai Launcher ===

REM Detect Python
if exist ".venv\Scripts\python.exe" (
    set PYTHON=.venv\Scripts\python.exe
    echo Using venv Python
) else (
    set PYTHON=py -3.11
    echo Using system Python (py -3.11)
)

REM Argument handling
if "%1"=="demo" (
    echo Starting in DEMO mode...
    %PYTHON% -u main.py --demo
) else (
    echo Starting Misora_ai...
    %PYTHON% -u main.py
)

echo.
echo Process exited.
pause
