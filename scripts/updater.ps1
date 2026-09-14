$ErrorActionPreference = 'Stop'
$Host.UI.RawUI.WindowTitle = 'PassportVault Updater'

# ── Resolve project root (one level up from scripts/) ────────────────────────
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ProjectRoot = Split-Path -Parent $ScriptDir

Write-Host ''
Write-Host '================================================================================'
Write-Host '  PASSPORTVAULT UPDATER — Test, Sync, Rebuild, Deploy'
Write-Host '================================================================================'
Write-Host "  Project : $ProjectRoot"
Write-Host "  Time    : $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Write-Host '================================================================================'
Write-Host ''

# ── Helper: run a command and stop if it fails ────────────────────────────────
function Invoke-Step {
    param(
        [string]$StepName,
        [scriptblock]$Command
    )
    Write-Host ''
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    Write-Host "  STEP: $StepName"
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    Write-Host ''

    & $Command

    if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) {
        Write-Host ''
        Write-Host "  ██ FAILED: $StepName (exit code $LASTEXITCODE)" -ForegroundColor Red
        Write-Host "  ██ Stopping updater. Fix the issue above and re-run." -ForegroundColor Red
        Write-Host ''
        exit $LASTEXITCODE
    }
    Write-Host ''
    Write-Host "  ✓ $StepName — PASSED" -ForegroundColor Green
}

# ══════════════════════════════════════════════════════════════════════════════
#  STEP 1: Run unit tests locally (using venv Python)
# ══════════════════════════════════════════════════════════════════════════════
Invoke-Step 'Run Unit Tests (local)' {
    $venvPython = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path $venvPython)) {
        Write-Host '  WARNING: .venv not found, trying system python...' -ForegroundColor Yellow
        $venvPython = 'python'
    }
    & $venvPython (Join-Path $ProjectRoot 'run_tests.py')
}

# ══════════════════════════════════════════════════════════════════════════════
#  STEP 2: Verify WSL Ubuntu is running
# ══════════════════════════════════════════════════════════════════════════════
Invoke-Step 'Check WSL Ubuntu availability' {
    $ErrorActionPreference = 'Continue'
    & wsl.exe -d Ubuntu --exec true 2>$null
    $wslOk = ($LASTEXITCODE -eq 0)
    $ErrorActionPreference = 'Stop'
    if (-not $wslOk) {
        Write-Host '  ERROR: WSL Ubuntu is not available. Start it first.' -ForegroundColor Red
        $global:LASTEXITCODE = 1
        return
    }
    Write-Host '  WSL Ubuntu is running.'
    $global:LASTEXITCODE = 0
}

# ══════════════════════════════════════════════════════════════════════════════
#  STEP 3: Copy / sync project files into WSL (/opt/passportvault)
# ══════════════════════════════════════════════════════════════════════════════
Invoke-Step 'Sync project files to WSL (/opt/passportvault)' {
    # Convert Windows path to WSL path
    $wslSourcePath = (& wsl.exe -d Ubuntu --exec wslpath -a $ProjectRoot).Trim()
    if (-not $wslSourcePath) {
        Write-Host '  ERROR: Could not convert project path to WSL path.' -ForegroundColor Red
        $global:LASTEXITCODE = 1
        return
    }
    Write-Host "  Source (WSL mount) : $wslSourcePath"
    Write-Host "  Destination        : /opt/passportvault"
    Write-Host ''

    # rsync project files, excluding .git, .venv, __pycache__, etc.
    & wsl.exe -d Ubuntu -u root -- bash -lc "
        mkdir -p /opt/passportvault && \
        rsync -av --delete \
            --exclude='.git/' \
            --exclude='.venv/' \
            --exclude='__pycache__/' \
            --exclude='*.pyc' \
            --exclude='*.sqlite3' \
            --exclude='node_modules/' \
            --exclude='.env' \
            '$wslSourcePath/' /opt/passportvault/ && \
        echo '' && echo 'Files synced successfully.'
    "
}

# ══════════════════════════════════════════════════════════════════════════════
#  STEP 4: Fix line endings inside WSL (CRLF → LF)
# ══════════════════════════════════════════════════════════════════════════════
Invoke-Step 'Fix CRLF line endings in WSL' {
    & wsl.exe -d Ubuntu -u root -- bash -lc "
        cd /opt/passportvault && \
        find . -name '*.py' -o -name '*.sh' -o -name '*.yml' -o -name '*.yaml' -o -name '*.toml' -o -name '*.cfg' -o -name '*.txt' -o -name '*.md' -o -name 'Dockerfile' -o -name 'Caddyfile' -o -name '*.lock' | \
        xargs -r sed -i 's/\r$//' 2>/dev/null && \
        echo 'Line endings fixed.'
    "
}

# ══════════════════════════════════════════════════════════════════════════════
#  STEP 5: Rebuild Docker containers
# ══════════════════════════════════════════════════════════════════════════════
Invoke-Step 'Rebuild Docker containers (docker compose build)' {
    & wsl.exe -d Ubuntu -u root -- bash -lc "
        cd /opt/passportvault && \
        docker compose build --no-cache
    "
}

# ══════════════════════════════════════════════════════════════════════════════
#  STEP 6: Deploy — restart containers with new images
# ══════════════════════════════════════════════════════════════════════════════
Invoke-Step 'Deploy new containers (docker compose up -d)' {
    & wsl.exe -d Ubuntu -u root -- bash -lc "
        cd /opt/passportvault && \
        docker compose up -d
    "
}

# ══════════════════════════════════════════════════════════════════════════════
#  STEP 7: Wait for the web container to be healthy
# ══════════════════════════════════════════════════════════════════════════════
Invoke-Step 'Wait for web container to be ready' {
    $ready = $false
    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Seconds 2
        try {
            $code = (& curl.exe -k -s -o NUL -w '%{http_code}' 'https://localhost:8443').Trim()
            if ($code -eq '200' -or $code -eq '302') {
                $ready = $true
                break
            }
        } catch { }
        Write-Host "  Waiting... ($($i+1)/30)"
    }
    if (-not $ready) {
        Write-Host '  ERROR: Web container did not become ready within 60 seconds.' -ForegroundColor Red
        & wsl.exe -d Ubuntu -u root -- bash -lc 'cd /opt/passportvault && docker compose logs --tail=30 web'
        $global:LASTEXITCODE = 1
        return
    }
    Write-Host '  Web container is responding at https://localhost:8443'
    $global:LASTEXITCODE = 0
}

# ══════════════════════════════════════════════════════════════════════════════
#  STEP 8: Run diagnostic harness inside Docker
# ══════════════════════════════════════════════════════════════════════════════
Invoke-Step 'Run diagnostic harness inside Docker' {
    $diagScript = Join-Path $ProjectRoot 'scripts\diagnose_records.py'
    if (Test-Path $diagScript) {
        Get-Content $diagScript -Raw | wsl.exe -d Ubuntu -u root -- bash -lc 'cd /opt/passportvault && docker compose exec -T web python -'
    } else {
        Write-Host '  SKIP: diagnose_records.py not found.' -ForegroundColor Yellow
        $global:LASTEXITCODE = 0
    }
}

# ══════════════════════════════════════════════════════════════════════════════
#  DONE
# ══════════════════════════════════════════════════════════════════════════════
Write-Host ''
Write-Host '================================================================================'
Write-Host '  ALL STEPS COMPLETED SUCCESSFULLY' -ForegroundColor Green
Write-Host '================================================================================'
Write-Host "  Dashboard: https://localhost:8443"
Write-Host "  Time     : $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Write-Host '================================================================================'
Write-Host ''
