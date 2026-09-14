@echo off
setlocal
echo === Running WSL distributions ===
wsl --list --running
echo.
echo === PassportVault containers ===
wsl -d Ubuntu -u root -- bash -lc "cd /opt/passportvault 2>/dev/null && docker compose ps || true"
echo.
echo === Windows localhost HTTPS ===
curl.exe -k -I https://localhost:8443
pause
endlocal
