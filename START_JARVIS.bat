@echo off
title J.A.R.V.I.S. Desktop
cd /d "%~dp0"
if exist "%~dp0venv\Scripts\python.exe" (
    start "" "%~dp0venv\Scripts\python.exe" "%~dp0jarvis_app.py"
) else (
    start "" python "%~dp0jarvis_app.py"
)
if errorlevel 1 (
    echo.
    echo J.A.R.V.I.S. konnte nicht gestartet werden.
    pause
)
