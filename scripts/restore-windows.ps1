$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.OpenFileDialog
$dialog.Filter = 'Encrypted Passport Vault backups (*.age)|*.age'
$dialog.Title = 'Select a Passport Vault backup - restore replaces current data'
if ($dialog.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) { return }
$source = (& wsl.exe -d Ubuntu --exec wslpath -a $dialog.FileName).Trim()
& wsl.exe -d Ubuntu -u root --exec bash /opt/passportvault/scripts/restore-linux.sh $source
if ($LASTEXITCODE -ne 0) { throw 'Restore stopped. Send a screenshot; do not delete the backup or old installation.' }
Start-Process 'https://localhost:8443'
