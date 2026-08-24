$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $ProjectRoot "backend"
$Frontend = Join-Path $ProjectRoot "frontend"
$PythonExe = Join-Path $Backend ".venv\Scripts\python.exe"

Write-Host ""
Write-Host "=== PayTrace AI setup ===" -ForegroundColor Cyan

if (-not (Test-Path $PythonExe)) {
    Write-Host "Creating backend virtual environment..."
    Push-Location $Backend

    if (Get-Command py -ErrorAction SilentlyContinue) {
        py -m venv .venv
    }
    elseif (Get-Command python -ErrorAction SilentlyContinue) {
        python -m venv .venv
    }
    else {
        Pop-Location
        throw "Python was not found in PATH."
    }

    Pop-Location
}

Write-Host "Installing backend requirements..."
& $PythonExe -m pip install --upgrade pip
& $PythonExe -m pip install -r (Join-Path $Backend "requirements.txt")

Write-Host "Installing frontend packages..."
Push-Location $Frontend
npm install
Pop-Location

$BackendEnv = Join-Path $Backend ".env"
$BackendExample = Join-Path $Backend ".env.example"

if (-not (Test-Path $BackendEnv)) {
    Copy-Item $BackendExample $BackendEnv
    Write-Host ""
    Write-Host "Created backend/.env from .env.example." -ForegroundColor Yellow
    Write-Host "Fill in Razorpay Test Mode credentials before starting PayTrace." -ForegroundColor Yellow
}

$FrontendEnv = Join-Path $Frontend ".env"
$FrontendExample = Join-Path $Frontend ".env.example"

if (-not (Test-Path $FrontendEnv)) {
    Copy-Item $FrontendExample $FrontendEnv
}

Write-Host ""
Write-Host "Setup complete." -ForegroundColor Green
Write-Host "Next:"
Write-Host "  1. Edit backend/.env"
Write-Host "  2. .\scripts\start_backend.ps1"
Write-Host "  3. .\scripts\start_frontend.ps1"
Write-Host "  4. Start zrok and update the Razorpay Test Mode webhook URL"
