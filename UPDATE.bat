@echo off
setlocal
set "VAULT_PACKAGE=%~dp0"
echo.
echo  PassportVault Updater - launching...
echo.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\updater.ps1"
if errorlevel 1 (
    echo.
    echo  UPDATE FAILED. See the error above.
    echo.
)
pause
endlocal
