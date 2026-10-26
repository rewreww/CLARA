[CmdletBinding()]
param(
    [switch]$NoBrowser,
    [switch]$LegacyParser,
    [switch]$WithOllama,
    [switch]$Check,
    [ValidateRange(15, 900)][int]$TimeoutSeconds = 180
)
$pythonPath = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    Write-Error 'CLARA virtual environment is missing. Follow docs/README.md first-time setup.'
    exit 1
}
$launcherArguments = @((Join-Path $PSScriptRoot 'scripts\clara_launcher.py'), 'start', '--timeout', "$TimeoutSeconds")
if ($NoBrowser) { $launcherArguments += '--no-browser' }
if ($LegacyParser) { $launcherArguments += '--legacy-parser' }
if ($WithOllama) { $launcherArguments += '--with-ollama' }
if ($Check) { $launcherArguments += '--check' }
& $pythonPath @launcherArguments
exit $LASTEXITCODE
