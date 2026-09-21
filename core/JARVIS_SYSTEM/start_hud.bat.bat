@echo off
title J.A.R.V.I.S. MARK XXXIX HUD
cd /d "%~dp0"
echo Pruefe Abhaengigkeiten...
pip install --upgrade customtkinter psutil pyttsx3 python-dotenv google-genai >nul 2>&1
echo ----------------------------------------
echo STARTE HUD BENUTZEROBERFLAECHE, SIR...
echo ----------------------------------------
python -B gui_jarvis.py
pause
