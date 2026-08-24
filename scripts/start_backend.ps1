$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $ProjectRoot "backend"
$VenvPython = Join-Path $Backend ".venv\Scripts\python.exe"

Push-Location $Backend

try {
    if (Test-Path $VenvPython) {
        & $VenvPython -m uvicorn app.main:app --reload
    }
    else {
        Write-Host "backend/.venv was not found; using Python from PATH." -ForegroundColor Yellow
        python -m uvicorn app.main:app --reload
    }
}
finally {
    Pop-Location
}
