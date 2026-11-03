$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$pythonPath = Join-Path $projectRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Create .venv and install requirements-web.txt first. See docs/WEB_POSTGRESQL.md.'
}
$env:PYTHONUTF8 = '1'
& $pythonPath -m uvicorn app.main:app --host 127.0.0.1 --port 8000
