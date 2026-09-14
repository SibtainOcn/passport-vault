$ErrorActionPreference = 'Stop'
$Host.UI.RawUI.WindowTitle = 'PassportVault Updater'

# -- Resolve project root (one level up from scripts/) ------------------------
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ProjectRoot = Split-Path -Parent $ScriptDir

Write-Host ''
Write-Host '================================================================================'
Write-Host '  PASSPORTVAULT UPDATER -- Sync, Rebuild, Deploy & Verify'
Write-Host '================================================================================'
Write-Host "  Project : $ProjectRoot"
Write-Host "  Time    : $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Write-Host '================================================================================'
Write-Host ''

# -- Helper: run a command and stop if it fails --------------------------------
function Invoke-Step {
    param(
        [string]$StepName,
        [scriptblock]$Command,
        [switch]$AllowWarning
    )
    Write-Host ''
    Write-Host '--------------------------------------------------------------------------------'
    Write-Host "  STEP: $StepName"
    Write-Host '--------------------------------------------------------------------------------'
    Write-Host ''

    & $Command

    if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) {
        if ($AllowWarning) {
            Write-Host ''
            Write-Host "  [WARNING] $StepName completed with exit code $LASTEXITCODE (continuing to Docker verification)..." -ForegroundColor Yellow
            Write-Host ''
            $global:LASTEXITCODE = 0
            return
        }
        Write-Host ''
        Write-Host "  [FAILED] $StepName (exit code $LASTEXITCODE)" -ForegroundColor Red
        Write-Host '  Stopping updater. Fix the issue above and re-run.' -ForegroundColor Red
        Write-Host ''
        exit $LASTEXITCODE
    }
    Write-Host ''
    Write-Host "  [OK] $StepName -- PASSED" -ForegroundColor Green
}

# ==============================================================================
#  STEP 0: Pull latest changes from Git (if inside a git repository)
# ==============================================================================
Invoke-Step 'Pull latest Git updates' -AllowWarning {
    if (Test-Path (Join-Path $ProjectRoot '.git')) {
        $gitCmd = Get-Command git.exe -ErrorAction SilentlyContinue
        if ($gitCmd) {
            Write-Host '  Pulling latest changes from remote repository...'
            & git.exe -C $ProjectRoot pull --ff-only
            if ($LASTEXITCODE -ne 0) {
                Write-Host '  git pull completed (or already up to date).' -ForegroundColor Yellow
            }
        } else {
            Write-Host '  git.exe not found in PATH; skipping git pull.' -ForegroundColor Yellow
        }
    } else {
        Write-Host '  Not a git working copy; skipping git pull.'
    }
    $global:LASTEXITCODE = 0
}

# ==============================================================================
#  STEP 1: Run unit tests locally (auto-detect .venv OR global system Python)
# ==============================================================================
Invoke-Step 'Run Unit Tests (local pre-flight)' -AllowWarning {
    $resolvedPython = $null
    $pythonLabel = ''

    # 1. Check local virtual environment (.venv)
    $venvPython = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
    if (Test-Path $venvPython) {
        $resolvedPython = $venvPython
        $pythonLabel = 'Local virtual environment (.venv)'
    }

    # 2. Check active virtual environment ($env:VIRTUAL_ENV)
    if (-not $resolvedPython -and $env:VIRTUAL_ENV) {
        $activePython = Join-Path $env:VIRTUAL_ENV 'Scripts\python.exe'
        if (Test-Path $activePython) {
            $resolvedPython = $activePython
            $pythonLabel = 'Active virtual environment (VIRTUAL_ENV)'
        }
    }

    # 3. Check system Python in PATH
    if (-not $resolvedPython) {
        $cmdPython = Get-Command python.exe -ErrorAction SilentlyContinue
        if ($cmdPython -and $cmdPython.Source -notmatch 'WindowsApps') {
            $resolvedPython = $cmdPython.Source
            $pythonLabel = 'System Python (PATH)'
        }
    }

    # 4. Check common global Python installation directories
    if (-not $resolvedPython) {
        $commonLocations = @(
            "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
            "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
            "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
            "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe",
            "$env:ProgramFiles\Python313\python.exe",
            "$env:ProgramFiles\Python312\python.exe",
            "$env:ProgramFiles\Python311\python.exe",
            "$env:ProgramFiles\Python310\python.exe",
            "C:\Python313\python.exe",
            "C:\Python312\python.exe",
            "C:\Python311\python.exe",
            "C:\Python310\python.exe"
        )
        foreach ($loc in $commonLocations) {
            if (Test-Path $loc) {
                $resolvedPython = $loc
                $pythonLabel = "Installed Python ($loc)"
                break
            }
        }
    }

    if ($resolvedPython) {
        Write-Host "  Using Python interpreter: $resolvedPython [$pythonLabel]"
        & $resolvedPython (Join-Path $ProjectRoot 'run_tests.py')
    } else {
        Write-Host '  No local Python found on host machine. Unit tests will run inside Docker container.' -ForegroundColor Yellow
        $global:LASTEXITCODE = 0
    }
}

# ==============================================================================
#  STEP 2: Ensure WSL Ubuntu is running (auto-start if stopped)
# ==============================================================================
Invoke-Step 'Ensure WSL Ubuntu is running' {
    $ErrorActionPreference = 'Continue'
    & wsl.exe -d Ubuntu --exec true 2>$null
    $wslOk = ($LASTEXITCODE -eq 0)
    $ErrorActionPreference = 'Stop'

    if (-not $wslOk) {
        Write-Host '  WSL Ubuntu is not running. Attempting to start...' -ForegroundColor Yellow

        $ErrorActionPreference = 'Continue'
        & wsl.exe -d Ubuntu -- echo 'WSL started' 2>$null
        $startOk = ($LASTEXITCODE -eq 0)
        $ErrorActionPreference = 'Stop'

        if (-not $startOk) {
            Write-Host '  WSL still not responding. Trying wsl --shutdown and restart...' -ForegroundColor Yellow
            & wsl.exe --shutdown 2>$null
            Start-Sleep -Seconds 3
            $ErrorActionPreference = 'Continue'
            & wsl.exe -d Ubuntu -- echo 'WSL restarted' 2>$null
            $restartOk = ($LASTEXITCODE -eq 0)
            $ErrorActionPreference = 'Stop'

            if (-not $restartOk) {
                Write-Host '  ERROR: Cannot start WSL Ubuntu. Is it installed?' -ForegroundColor Red
                Write-Host '  Run: wsl --install -d Ubuntu' -ForegroundColor Red
                $global:LASTEXITCODE = 1
                return
            }
        }
        Write-Host '  WSL Ubuntu started successfully.'
    } else {
        Write-Host '  WSL Ubuntu is already running.'
    }

    # Make sure Docker service is running inside WSL
    Write-Host '  Ensuring Docker service is running inside WSL...'
    & wsl.exe -d Ubuntu -u root -- bash -lc 'service docker start 2>/dev/null || true'
    Start-Sleep -Seconds 2

    # Verify Docker is responsive
    $ErrorActionPreference = 'Continue'
    & wsl.exe -d Ubuntu -u root -- bash -lc 'docker info > /dev/null 2>&1'
    $dockerOk = ($LASTEXITCODE -eq 0)
    $ErrorActionPreference = 'Stop'

    if (-not $dockerOk) {
        Write-Host '  ERROR: Docker is not responding inside WSL.' -ForegroundColor Red
        Write-Host '  Try: wsl -d Ubuntu -u root -- service docker start' -ForegroundColor Red
        $global:LASTEXITCODE = 1
        return
    }
    Write-Host '  Docker is running inside WSL.'
    $global:LASTEXITCODE = 0
}

# ==============================================================================
#  STEP 3: Copy / sync project files into WSL (/opt/passportvault) (IMG 1 - Step 2)
# ==============================================================================
Invoke-Step 'Sync project files to WSL (/opt/passportvault)' {
    $wslSourcePath = (& wsl.exe -d Ubuntu --exec wslpath -a $ProjectRoot).Trim()
    if (-not $wslSourcePath) {
        Write-Host '  ERROR: Could not convert project path to WSL path.' -ForegroundColor Red
        $global:LASTEXITCODE = 1
        return
    }
    Write-Host "  Source (WSL mount) : $wslSourcePath"
    Write-Host "  Destination        : /opt/passportvault"
    Write-Host ''

    $rsyncCmd = "mkdir -p /opt/passportvault && rsync -av --delete --exclude='secrets/' --exclude='db-tls/' --exclude='db-init/' --exclude='backups/' --exclude='.sites-runtime/' --exclude='.git/' --exclude='.venv/' --exclude='__pycache__/' --exclude='*.pyc' --exclude='*.sqlite3' --exclude='node_modules/' --exclude='.env' '$wslSourcePath/' /opt/passportvault/ && chmod 700 /opt/passportvault && echo 'Files synced successfully.'"
    & wsl.exe -d Ubuntu -u root -- bash -c $rsyncCmd
}

# ==============================================================================
#  STEP 4: Fix line endings inside WSL (CRLF -> LF)
# ==============================================================================
Invoke-Step 'Fix CRLF line endings in WSL' {
    $fixCrlfCmd = "cd /opt/passportvault && find . -type f \( -name '*.py' -o -name '*.sh' -o -name '*.yml' -o -name '*.yaml' -o -name '*.toml' -o -name '*.cfg' -o -name '*.txt' -o -name '*.md' -o -name 'Dockerfile' -o -name 'Caddyfile' -o -name '*.lock' \) -exec sed -i 's/\r$//' {} + && echo 'Line endings fixed.'"
    & wsl.exe -d Ubuntu -u root -- bash -c $fixCrlfCmd
}

# ==============================================================================
#  STEP 5: Rebuild Docker containers and restart (IMG 2 - Step 3)
# ==============================================================================
Invoke-Step 'Rebuild Docker containers and restart' {
    $rebuildCmd = "cd /opt/passportvault && docker compose build web worker && docker compose up -d --force-recreate"
    & wsl.exe -d Ubuntu -u root -- bash -c $rebuildCmd
}

# ==============================================================================
#  STEP 6: Wait for web container to be ready
# ==============================================================================
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
        & wsl.exe -d Ubuntu -u root -- bash -c "cd /opt/passportvault && docker compose logs --tail=30 web"
        $global:LASTEXITCODE = 1
        return
    }
    Write-Host '  Web container is responding at https://localhost:8443'

    # Apply any pending database migrations
    Write-Host '  Applying database migrations...'
    & wsl.exe -d Ubuntu -u root -- bash -c "cd /opt/passportvault && docker compose exec -T web python manage.py migrate --noinput"

    # Ensure the background keepalive process is running (from start-windows.ps1)
    $check = & wsl.exe -d Ubuntu -u root --exec bash -c 'test -f /tmp/passportvault-keepalive.pid && kill -0 "$(cat /tmp/passportvault-keepalive.pid)" 2>/dev/null; echo $?'
    $keeperRunning = (($check | Select-Object -Last 1).Trim() -eq '0')
    if (-not $keeperRunning) {
        $linux = 'service docker start >/dev/null 2>&1 || true; cd /opt/passportvault || exit 1; docker compose up -d || exit 1; echo $$ > /tmp/passportvault-keepalive.pid; trap "rm -f /tmp/passportvault-keepalive.pid" EXIT; exec sleep infinity'
        Start-Process -FilePath 'wsl.exe' -ArgumentList @('-d','Ubuntu','-u','root','--exec','bash','-c',$linux) -WindowStyle Minimized | Out-Null
        Write-Host '  Background WSL keepalive process initialized.'
    }
    $global:LASTEXITCODE = 0
}

# ==============================================================================
#  STEP 7: Re-verify existing documents with new logic (IMG 2 - Step 4)
# ==============================================================================
Invoke-Step 'Re-verify existing documents with new tiered logic' {
    & wsl.exe -d Ubuntu -u root -- bash -c "cd /opt/passportvault && docker compose exec -T web python scripts/reverify_all.py"
}

# ==============================================================================
#  STEP 8: Run diagnostic harness inside Docker (IMG 3 - Step 5)
# ==============================================================================
Invoke-Step 'Run diagnostic harness inside Docker' {
    & wsl.exe -d Ubuntu -u root -- bash -c "cd /opt/passportvault && docker compose exec -T web python scripts/diagnose_records.py"
}

# ==============================================================================
#  STEP 9: Run unit tests inside Docker container (full verification)
# ==============================================================================
Invoke-Step 'Run unit tests inside Docker container' {
    & wsl.exe -d Ubuntu -u root -- bash -c "cd /opt/passportvault && docker compose exec -T web python run_tests.py"
}

# ==============================================================================
#  DONE
# ==============================================================================
Write-Host ''
Write-Host '================================================================================'
Write-Host '  ALL STEPS COMPLETED SUCCESSFULLY' -ForegroundColor Green
Write-Host '================================================================================'
Write-Host "  Dashboard: https://localhost:8443"
Write-Host "  Time     : $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Write-Host '================================================================================'
Write-Host ''
