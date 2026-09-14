$ErrorActionPreference = 'Stop'
& wsl.exe -d Ubuntu -u root --exec bash -lc 'cd /opt/passportvault && docker compose stop; if [ -f /tmp/passportvault-keepalive.pid ]; then pid=$(cat /tmp/passportvault-keepalive.pid); rm -f /tmp/passportvault-keepalive.pid; kill "$pid" 2>/dev/null || true; fi'
if ($LASTEXITCODE -ne 0) { throw 'Could not stop the application.' }
Write-Host 'Stopped. Records, keys and Docker volumes are preserved.'
