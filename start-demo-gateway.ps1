[CmdletBinding()]
param()
$pythonPath = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'CLARA Python environment is missing.' }
& $pythonPath (Join-Path $PSScriptRoot 'scripts\prepare_demo.py')
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host 'Starting protected demo gateway on 127.0.0.1:8765. Keep this terminal open; Ctrl+C stops it.'
& $pythonPath (Join-Path $PSScriptRoot 'scripts\demo_gateway.py')
exit $LASTEXITCODE
