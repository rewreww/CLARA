[CmdletBinding()]
param([switch]$RestorePowerSettings)
$ErrorActionPreference = 'Stop'
$deployment = Join-Path (Split-Path $PSScriptRoot -Parent) '.clara\deployment'
New-Item -ItemType File -Path (Join-Path $deployment 'watchdog.stop') -Force | Out-Null
Disable-ScheduledTask -TaskName 'CLARA Demo Watchdog' | Out-Null
Stop-ScheduledTask -TaskName 'CLARA Demo Watchdog'
Unregister-ScheduledTask -TaskName 'CLARA Demo Watchdog' -Confirm:$false
if ($RestorePowerSettings) {
    $backup = Get-Content -LiteralPath (Join-Path $deployment 'power-before-watchdog.json') -Raw | ConvertFrom-Json
    foreach ($setting in $backup.Settings) {
        powercfg /setacvalueindex $backup.Scheme $setting.Subgroup $setting.Setting $setting.Value
        if ($LASTEXITCODE -ne 0) { throw 'Failed to restore power setting.' }
    }
    powercfg /setactive $backup.Scheme
}
Write-Host 'Demo watchdog removed. Local CLARA services remain managed by start-clara.ps1 / stop-clara.ps1.'
