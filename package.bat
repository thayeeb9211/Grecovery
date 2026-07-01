@echo off
cd /d "%~dp0"

echo ============================================
echo   Grecovery Packager
echo ============================================
echo.

set ZIP_NAME=Grecovery.zip

if exist "%ZIP_NAME%" del "%ZIP_NAME%"

echo Packaging files...

powershell -NoProfile -Command ^
    "Compress-Archive -Path 'run.bat','updater.ps1','version.txt','app.py','requirements.txt','README.md','templates' -DestinationPath '%ZIP_NAME%' -Force"

if %errorlevel% neq 0 (
    echo ERROR: Packaging failed.
    pause
    exit /b 1
)

echo.
echo ============================================
echo   DONE
echo   Output : %ZIP_NAME%
echo   Share this file with your team.
echo ============================================
echo.

pause
