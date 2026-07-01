@echo off
cd /d "%~dp0"

echo ============================================
echo   Grecovery Launcher
echo ============================================
echo.

REM ── Auto-update check ──
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0updater.ps1"
echo.

REM ── Check if Python is already installed ──
python --version >nul 2>&1
if %errorlevel% equ 0 goto :check_deps

echo Python not found. Attempting automatic installation...
echo.

REM ── Try winget (built into Windows 10 1709+ / Windows 11) ──
winget --version >nul 2>&1
if %errorlevel% equ 0 (
    echo Installing Python 3.11 via winget...
    winget install -e --id Python.Python.3.11 --silent --accept-package-agreements --accept-source-agreements
    REM Refresh PATH from registry without restarting
    for /f "tokens=*" %%p in ('powershell -NoProfile -Command "[Environment]::GetEnvironmentVariable(\"Path\",\"Machine\") + \";\" + [Environment]::GetEnvironmentVariable(\"Path\",\"User\")"') do set "PATH=%%p"
    python --version >nul 2>&1
    if %errorlevel% equ 0 goto :check_deps
)

REM ── Fallback: download Python 3.11 installer directly ──
echo winget unavailable. Downloading Python 3.11 installer from python.org...
powershell -NoProfile -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe' -OutFile '%TEMP%\python_setup.exe' -UseBasicParsing"
if %errorlevel% neq 0 (
    echo.
    echo ERROR: Download failed. Check your internet connection.
    echo Install Python manually from https://www.python.org/downloads/
    pause
    exit /b 1
)
echo Installing Python silently (this may take a minute)...
"%TEMP%\python_setup.exe" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0
del "%TEMP%\python_setup.exe" >nul 2>&1

REM Refresh PATH again
for /f "tokens=*" %%p in ('powershell -NoProfile -Command "[Environment]::GetEnvironmentVariable(\"Path\",\"Machine\") + \";\" + [Environment]::GetEnvironmentVariable(\"Path\",\"User\")"') do set "PATH=%%p"

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo ERROR: Installation completed but Python still not found in PATH.
    echo Please restart your computer and run this file again.
    pause
    exit /b 1
)

:check_deps
echo Python ready. Installing required packages...
pip install -r requirements.txt --quiet --disable-pip-version-check
if %errorlevel% neq 0 (
    echo WARNING: Some packages may not have installed. Trying to continue...
)

echo.
echo Starting Grecovery...
echo.
python app.py
if %errorlevel% neq 0 (
    echo.
    echo ERROR: Grecovery stopped unexpectedly. See details above.
    pause
)
