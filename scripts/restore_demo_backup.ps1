param(
    [string]$Backup
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $ProjectRoot "backend"

$Listener = Get-NetTCPConnection `
    -LocalPort 8000 `
    -State Listen `
    -ErrorAction SilentlyContinue

if ($Listener) {
    Write-Host "Stop the PayTrace backend before restoring data." -ForegroundColor Yellow
    exit 1
}

$Candidates = @(
    (Join-Path $Backend ".venv\Scripts\python.exe"),
    (Join-Path $ProjectRoot ".venv\Scripts\python.exe"),
    (Join-Path $Backend "venv\Scripts\python.exe"),
    (Join-Path $ProjectRoot "venv\Scripts\python.exe")
)

$PythonExe = $null

foreach ($Candidate in $Candidates) {
    if (Test-Path $Candidate) {
        $PythonExe = $Candidate
        break
    }
}

if (-not $PythonExe) {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        $PythonExe = "py"
    }
    else {
        $PythonExe = "python"
    }
}

$RestoreScript = Join-Path $PSScriptRoot "restore_demo_backup.py"

if ($Backup) {
    & $PythonExe $RestoreScript $Backup
}
else {
    & $PythonExe $RestoreScript
}
