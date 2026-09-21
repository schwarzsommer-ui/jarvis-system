@echo off
title JARVIS Edge TradingView Bridge
echo.
echo Schließe alle normalen Edge-Fenster manuell, falls Edge bereits läuft.
echo Danach wird dein normales Edge-Profil mit Remote-Steuerung gestartet.
echo.
tasklist /fi "imagename eq msedge.exe" | find /i "msedge.exe" >nul
if not errorlevel 1 (
    echo.
    echo Edge laeuft noch. Bitte alle Edge-Fenster schliessen und diese Datei erneut starten.
    echo Auch Edge-Hintergrundprozesse muessen beendet sein.
    pause
    exit /b 1
)
set "EDGE_EXE=%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"
if not exist "%EDGE_EXE%" set "EDGE_EXE=%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"
if not exist "%EDGE_EXE%" set "EDGE_EXE=%LocalAppData%\Microsoft\Edge\Application\msedge.exe"
if not exist "%EDGE_EXE%" (
    echo Microsoft Edge wurde nicht gefunden.
    pause
    exit /b 1
)
set "JARVIS_EDGE_CDP_URL=http://127.0.0.1:9222"
rem Use an isolated automation profile so JARVIS cannot alter the normal Edge profile.
set "EDGE_USER_DATA=%~dp0data\jarvis_edge_cdp_profile"
start "" "%EDGE_EXE%" --remote-debugging-port=9222 --remote-allow-origins=http://127.0.0.1:9222 --user-data-dir="%EDGE_USER_DATA%" --profile-directory=Default "https://www.tradingview.com/chart/?symbol=BTCUSD"
echo Edge wurde gestartet. Warte auf den Remote-Port...
set "READY="
for /l %%N in (1,1,20) do (
    powershell.exe -NoProfile -Command "try { Invoke-WebRequest -UseBasicParsing http://127.0.0.1:9222/json/version -TimeoutSec 1 | Out-Null; exit 0 } catch { exit 1 }"
    if not errorlevel 1 (
        set "READY=1"
        goto :edge_ready
    )
    timeout /t 1 /nobreak >nul
)
:edge_ready
if not defined READY (
    echo Edge-Remote-Debugging konnte nicht erreicht werden.
    pause
    exit /b 1
)
echo Edge bereit. Starte JARVIS...
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_jarvis.ps1"
if errorlevel 1 pause
