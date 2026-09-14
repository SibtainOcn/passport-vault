@echo off
setlocal
cd /d "%~dp0"
set "VAULT_PACKAGE=%~dp0"

echo.
echo ================================================================================
echo   PassportVault Updater
echo ================================================================================
echo.
echo  Checking for latest updates from Git...
git pull
echo.

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\updater.ps1"
if errorlevel 1 (
    echo.
    echo  UPDATE FAILED. See the error above.
    echo.
)
pause
endlocal
