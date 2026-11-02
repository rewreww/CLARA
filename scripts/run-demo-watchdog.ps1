$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $repoRoot
& (Join-Path $repoRoot '.venv\Scripts\python.exe') (Join-Path $PSScriptRoot 'demo_watchdog.py') *>> (Join-Path $repoRoot '.clara\deployment\watchdog-runner.log')
exit $LASTEXITCODE
