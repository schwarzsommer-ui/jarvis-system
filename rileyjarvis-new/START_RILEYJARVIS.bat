@echo off
setlocal
cd /d "%~dp0"

if not exist "node_modules" (
  echo Installing dependencies for the first start...
  call npm.cmd install
  if errorlevel 1 (
    echo.
    echo Installation failed. Make sure Node.js 20+ is installed.
    pause
    exit /b 1
  )
)

call npm.cmd run dev
if errorlevel 1 (
  echo.
  echo RileyJarvis could not be started.
  pause
)
