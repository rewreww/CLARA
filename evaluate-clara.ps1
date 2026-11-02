[CmdletBinding()]
param(
    [ValidateSet('Check','Score')][string]$Action = 'Check',
    [switch]$ReferencesReviewed,
    [string]$RunName = 'development',
    [string]$Resume
)
$ErrorActionPreference = 'Stop'
$python = Join-Path $PSScriptRoot '.clara\evaluation\venv\Scripts\python.exe'
$toolkit = Join-Path $PSScriptRoot 'evaluation\CLARA_Guideline_Evaluation'
$pilot = Join-Path $PSScriptRoot '.clara\evaluation\pilot'
if (-not (Test-Path -LiteralPath $python)) { throw 'The isolated Ragas environment is missing.' }
$arguments = @((Join-Path $toolkit 'evaluate_guidelines.py'), $Action.ToLowerInvariant(),
    '--questions', (Join-Path $pilot 'draft_questions.jsonl'),
    '--outputs', (Join-Path $pilot 'captured_outputs.jsonl'),
    '--config', (Join-Path $pilot 'pipeline_config.json'),
    '--guidelines', (Join-Path $PSScriptRoot 'ai-services\guidelines'),
    '--results', (Join-Path $PSScriptRoot '.clara\evaluation\scores'),
    '--run-name', $RunName)
if (-not $ReferencesReviewed) { $arguments += '--reference-free' }
if ($Resume) { $arguments += @('--resume', $Resume) }
Push-Location -LiteralPath $toolkit
try {
    & $python -u -X utf8 @arguments
    $resultCode = $LASTEXITCODE
} finally { Pop-Location }
exit $resultCode
