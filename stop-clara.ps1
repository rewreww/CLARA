[CmdletBinding()]
param()
$pythonPath = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    Write-Error 'CLARA virtual environment is missing.'
    exit 1
}
& $pythonPath (Join-Path $PSScriptRoot 'scripts\clara_launcher.py') stop
exit $LASTEXITCODE
