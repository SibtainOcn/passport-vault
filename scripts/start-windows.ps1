$ErrorActionPreference = 'Stop'

# PassportVault uses the Docker Engine installed inside the Ubuntu WSL distro.
# Keep one WSL client process alive while the app is running; otherwise some
# Windows/WSL configurations stop the distro after the launching command exits,
# which makes https://localhost:8443 disappear on browser refresh.
$check = & wsl.exe -d Ubuntu -u root --exec bash -lc 'test -f /tmp/passportvault-keepalive.pid && kill -0 "$(cat /tmp/passportvault-keepalive.pid)" 2>/dev/null; echo $?'
$keeperRunning = (($check | Select-Object -Last 1).Trim() -eq '0')

if (-not $keeperRunning) {
    $linux = 'service docker start >/dev/null 2>&1 || true; cd /opt/passportvault || exit 1; docker compose up -d || exit 1; echo $$ > /tmp/passportvault-keepalive.pid; trap "rm -f /tmp/passportvault-keepalive.pid" EXIT; exec sleep infinity'
    Start-Process -FilePath 'wsl.exe' -ArgumentList @('-d','Ubuntu','-u','root','--exec','bash','-lc',$linux) -WindowStyle Minimized | Out-Null
}

$ready = $false
for ($i=0; $i -lt 35; $i++) {
    Start-Sleep -Seconds 1
    try {
        $code = (& curl.exe -k -s -o NUL -w '%{http_code}' 'https://localhost:8443').Trim()
        if ($code -eq '200' -or $code -eq '302') { $ready = $true; break }
    } catch { }
}
if (-not $ready) {
    throw 'Passport Vault started inside WSL but Windows localhost did not become ready. Run CHECK_STATUS.cmd and send the output.'
}
Write-Host 'Passport Vault is running. Keep it running until you use STOP.cmd.'
Start-Process 'https://localhost:8443'
