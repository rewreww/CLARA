[CmdletBinding(DefaultParameterSetName='Selected')]
param(
    [Parameter(Mandatory, ParameterSetName='Selected')]
    [ValidatePattern('^Patient_[0-9]{8}$')][string[]]$Patients,
    [Parameter(Mandatory, ParameterSetName='All')][switch]$All
)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
$folders = Invoke-RestMethod 'http://localhost:5000/api/pdfingestion/patients' -TimeoutSec 30
if ($All) {
    $Patients = @($folders.patients | Where-Object { $_ -match '^Patient_[0-9]{8}$' } | Sort-Object)
    if ($Patients.Count -ne 100) { throw "Expected 100 MIMIC folders; found $($Patients.Count). Check the configured source before importing." }
}
$outputDirectory = Join-Path $repoRoot '.clara\mimic-import'
New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
foreach ($patient in $Patients) {
    if ($patient -notin $folders.patients) { throw "Configured source does not contain $patient." }
    Write-Host "Importing $patient (completed unchanged PDFs are skipped)..."
    $body = @{ folderName = $patient } | ConvertTo-Json -Compress
    $result = Invoke-RestMethod 'http://localhost:5000/api/pdfingestion/sync' -Method Post -ContentType 'application/json' -Body $body -TimeoutSec 7200
    $logPath = Join-Path $outputDirectory ($patient + '.json')
    $result | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $logPath -Encoding UTF8
    Write-Host "$patient : $($result.filesSeen) PDFs, $($result.filesExtracted) parsed, $($result.filesUnchanged) unchanged, $($result.failedFiles) failures"
    if ($result.failedFiles -gt 0) { throw "Resolve failures in $logPath before continuing. Re-run this command to resume." }
}
Write-Host 'Import finished. Import success is not CSV or clinical validation. Follow docs/MIMIC_VALIDATION.md.'
