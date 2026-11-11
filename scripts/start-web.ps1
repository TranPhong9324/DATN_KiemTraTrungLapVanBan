$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$pythonPath = Join-Path $projectRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Create .venv and install requirements-web.txt first. See docs/WEB_POSTGRESQL.md.'
}
Get-Command npm.cmd -ErrorAction Stop | Out-Null
Push-Location -LiteralPath (Join-Path $projectRoot 'frontend')
try {
    if (-not (Test-Path -LiteralPath 'node_modules')) {
        & npm.cmd ci
        if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
    }
    & npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw 'React build failed.' }
}
finally { Pop-Location }
$env:PYTHONUTF8 = '1'
& $pythonPath -m uvicorn app.main:app --host 127.0.0.1 --port 8000
