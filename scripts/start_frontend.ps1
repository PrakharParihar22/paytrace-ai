$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Frontend = Join-Path $ProjectRoot "frontend"

Push-Location $Frontend

try {
    npm run dev
}
finally {
    Pop-Location
}
