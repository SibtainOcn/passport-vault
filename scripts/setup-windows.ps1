$ErrorActionPreference = 'Stop'
$package = $env:VAULT_PACKAGE
Write-Host 'Passport Vault - setup on this Windows computer'
Write-Host 'Installs Ubuntu/WSL if needed, free Linux software, then creates your owner login.'
$answer = Read-Host 'Continue with installation? Type YES'
if ($answer -cne 'YES') { return }
$ErrorActionPreference = 'Continue'
& wsl.exe -d Ubuntu --exec true 2>$null
$ubuntuReady = ($LASTEXITCODE -eq 0)
$ErrorActionPreference = 'Stop'
if (-not $ubuntuReady) {
    Write-Host 'Ubuntu is not ready. Windows may request administrator approval.'
    Start-Process wsl.exe -ArgumentList '--install','-d','Ubuntu' -Verb RunAs -Wait
    Write-Host 'Complete Ubuntu first launch if prompted. Restart Windows if requested, then run SETUP again.'
    return
}
$wslList = (& wsl.exe -l -v | Out-String)
if ($wslList -notmatch '(?m)^\s*\*?\s*Ubuntu\s+\S+\s+2\s*$') {
    #& wsl.exe --set-version Ubuntu 2
    #if ($LASTEXITCODE -ne 0) { throw 'WSL 2 could not be enabled. Send a screenshot; do not disable Windows security controls.' }
}
$linuxPath = (& wsl.exe -d Ubuntu --exec wslpath -a $package).Trim()
if ($LASTEXITCODE -ne 0 -or !$linuxPath) { throw 'Could not locate the extracted project folder.' }
& wsl.exe -d Ubuntu -u root --exec bash -c "sed -i 's/\r$//' '$linuxPath'/scripts/*.sh 2>/dev/null || true"
& wsl.exe -d Ubuntu -u root --exec bash "$linuxPath/scripts/install-linux.sh" "$linuxPath"
if ($LASTEXITCODE -ne 0) { throw 'Setup stopped. Send a screenshot of the last messages; existing data has been preserved.' }
$certPath = Join-Path $env:TEMP 'passportvault-root.crt'
$cert = & wsl.exe -d Ubuntu -u root --exec cat /tmp/passportvault-root.crt
if ($LASTEXITCODE -ne 0) { throw 'Could not read the local HTTPS certificate.' }
[IO.File]::WriteAllLines($certPath,[string[]]$cert,[Text.Encoding]::ASCII)
Write-Host 'The next step trusts this application local HTTPS certificate for your Windows user.'
$trust = Read-Host 'Import the local certificate? Type YES'
if ($trust -ceq 'YES') {
    & certutil.exe -user -addstore Root $certPath
    if ($LASTEXITCODE -ne 0) { throw 'Certificate import failed. Send a screenshot; do not bypass browser warnings.' }
    Remove-Item $certPath
} else { Write-Host 'Certificate was not imported. Do not enter passports until trusted HTTPS is configured.' }
Write-Host 'Starting Passport Vault with the persistent WSL launcher.'
$startScript = Join-Path $package 'scripts\start-windows.ps1'
& ([scriptblock]::Create([IO.File]::ReadAllText($startScript)))
