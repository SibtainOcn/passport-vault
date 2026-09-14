@echo off
setlocal
set "VAULT_PACKAGE=%~dp0"
powershell.exe -NoLogo -NoProfile -Command "& ([scriptblock]::Create([IO.File]::ReadAllText((Join-Path $env:VAULT_PACKAGE 'scripts\setup-windows.ps1'))))"
if errorlevel 1 echo Operation stopped. Please send a screenshot of the messages above.
pause
endlocal
