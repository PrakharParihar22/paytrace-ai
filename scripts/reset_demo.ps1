param(
    [switch]$ClearReliability,
    [switch]$NoBackup
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $ProjectRoot "backend"

Write-Host ""
Write-Host "=== PayTrace Demo Reset ===" -ForegroundColor Cyan

# Resetting runtime data while the API is serving requests can produce
# confusing demo state. Require port 8000 to be free first.
$Listener = Get-NetTCPConnection `
    -LocalPort 8000 `
    -State Listen `
    -ErrorAction SilentlyContinue

if ($Listener) {
    Write-Host ""
    Write-Host "PayTrace backend is still running on port 8000." -ForegroundColor Yellow
    Write-Host "Stop the backend with Ctrl+C, then run this command again."
    Write-Host ""
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
    elseif (Get-Command python -ErrorAction SilentlyContinue) {
        $PythonExe = "python"
    }
    else {
        throw "Python was not found."
    }
}

$ResetScript = Join-Path $PSScriptRoot "reset_demo.py"

$Arguments = @($ResetScript)

if ($ClearReliability) {
    $Arguments += "--clear-reliability"
}

if ($NoBackup) {
    $Arguments += "--no-backup"
}

Write-Host "Using Python: $PythonExe"
Write-Host ""

& $PythonExe @Arguments

if ($LASTEXITCODE -ne 0) {
    throw "PayTrace demo reset failed."
}

Write-Host "Next:" -ForegroundColor Green
Write-Host "  1. Start the backend"
Write-Host "  2. Start the frontend"
Write-Host "  3. Refresh Overview"
Write-Host "  4. Confirm Transactions/Incidents/Recovered/Fixes are 0"
Write-Host ""
