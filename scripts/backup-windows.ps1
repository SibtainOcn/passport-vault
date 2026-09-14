$ErrorActionPreference = 'Stop'
& wsl.exe -d Ubuntu -u root --exec bash /opt/passportvault/scripts/backup-linux.sh
if ($LASTEXITCODE -ne 0) { throw 'Backup failed. Keep existing backups and send a screenshot.' }
$destination = Join-Path $env:VAULT_PACKAGE 'Backups'
New-Item -ItemType Directory -Force -Path $destination | Out-Null
$linuxDestination = (& wsl.exe -d Ubuntu --exec wslpath -a $destination).Trim()
& wsl.exe -d Ubuntu -u root --exec python3 /opt/passportvault/scripts/copy-backup.py $linuxDestination
if ($LASTEXITCODE -ne 0) { throw 'Backup created but Windows copy failed. Keep the original in Ubuntu.' }
Write-Host 'Encrypted backup copied into the Backups folder. Store a copy on a separate protected drive.'
