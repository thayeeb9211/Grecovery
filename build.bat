@echo off
cd /d "%~dp0"

echo ============================================
echo   Grecovery Builder
echo ============================================
echo.

echo [1/4] Installing build dependencies...
pip install pyinstaller pillow --quiet --disable-pip-version-check
if %errorlevel% neq 0 ( echo ERROR: pip install failed. & pause & exit /b 1 )

echo [2/4] Generating icon...
python icon_gen.py
if %errorlevel% neq 0 ( echo ERROR: Icon generation failed. & pause & exit /b 1 )

echo [3/4] Building Grecovery.exe...
pyinstaller --onefile --windowed --icon=icon.ico --add-data "templates;templates" --name "Grecovery" --clean --noconfirm app.py
if %errorlevel% neq 0 ( echo ERROR: PyInstaller build failed. & pause & exit /b 1 )

echo [4/4] Packaging for distribution...
if exist "Grecovery_dist.zip" del "Grecovery_dist.zip"
powershell -NoProfile -Command "Compress-Archive -Path 'dist\Grecovery.exe' -DestinationPath 'Grecovery_dist.zip'"

echo.
echo ============================================
echo   BUILD COMPLETE
echo   Executable : dist\Grecovery.exe
echo   Zip bundle : Grecovery_dist.zip
echo ============================================
echo.

REM Offer to create a Desktop shortcut
set /p SHORTCUT="Create Desktop shortcut now? (y/n): "
if /i "%SHORTCUT%"=="y" (
    powershell -NoProfile -Command ^
        "$exe = (Resolve-Path 'dist\Grecovery.exe').Path; $ws = New-Object -ComObject WScript.Shell; $sc = $ws.CreateShortcut([System.IO.Path]::Combine($ws.SpecialFolders('Desktop'), 'Grecovery.lnk')); $sc.TargetPath = $exe; $sc.IconLocation = $exe; $sc.Description = 'Gateway Manual Recovery System'; $sc.Save(); Write-Host 'Desktop shortcut created.'"
)

pause
