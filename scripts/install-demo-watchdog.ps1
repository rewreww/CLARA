[CmdletBinding()]
param([switch]$KeepAwakeOnAC)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
$deployment = Join-Path $repoRoot '.clara\deployment'
$python = Join-Path $repoRoot '.venv\Scripts\python.exe'
$config = Join-Path $deployment 'watchdog.json'
if (-not (Test-Path -LiteralPath $python) -or -not (Test-Path -LiteralPath $config)) {
    throw 'Python or verified .clara/deployment/watchdog.json is missing.'
}
$saved = Get-Content -LiteralPath $config -Raw | ConvertFrom-Json
if (-not (Test-Path -LiteralPath $saved.devtunnel)) { throw 'Configured devtunnel executable is missing.' }
if (Test-Path -LiteralPath (Join-Path $deployment 'watchdog.stop')) {
    Remove-Item -LiteralPath (Join-Path $deployment 'watchdog.stop')
}

if ($KeepAwakeOnAC) {
    $backupPath = Join-Path $deployment 'power-before-watchdog.json'
    $schemeText = powercfg /getactivescheme | Out-String
    $scheme = [regex]::Match($schemeText, '[a-fA-F0-9]{8}(?:-[a-fA-F0-9]{4}){3}-[a-fA-F0-9]{12}').Value
    if (-not $scheme) { throw 'Cannot determine active power scheme.' }
    $settings = @(@('SUB_SLEEP','STANDBYIDLE'), @('SUB_SLEEP','HIBERNATEIDLE'), @('SUB_BUTTONS','LIDACTION'))
    $originals = foreach ($setting in $settings) {
        $detail = powercfg /qh $scheme $setting[0] $setting[1] | Out-String
        $match = [regex]::Match($detail, 'Current AC Power Setting Index:\s*0x([0-9a-fA-F]+)')
        if (-not $match.Success) { throw "Cannot back up power setting $($setting[1])." }
        [pscustomobject]@{ Subgroup=$setting[0]; Setting=$setting[1]; Value=[Convert]::ToInt32($match.Groups[1].Value,16) }
    }
    if (-not (Test-Path -LiteralPath $backupPath)) {
        @{ Scheme=$scheme; Settings=@($originals) } | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $backupPath -Encoding UTF8
    }
    foreach ($setting in $settings) {
        powercfg /setacvalueindex $scheme $setting[0] $setting[1] 0
        if ($LASTEXITCODE -ne 0) { throw "Failed to set $($setting[1])." }
    }
    powercfg /setactive $scheme
    if ($LASTEXITCODE -ne 0) { throw 'Failed to activate power settings.' }
}

$account = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$arguments = '-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + (Join-Path $PSScriptRoot 'run-demo-watchdog.ps1') + '"'
$action = New-ScheduledTaskAction -Execute "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -Argument $arguments -WorkingDirectory $repoRoot
$login = New-ScheduledTaskTrigger -AtLogOn -User $account
$retry = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 5)
$principal = New-ScheduledTaskPrincipal -UserId $account -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName 'CLARA Demo Watchdog' -Description 'Maintains the protected CLARA gateway and existing Microsoft Dev Tunnel, checks Vercel, and renews tunnel expiry.' -Action $action -Trigger @($login,$retry) -Principal $principal -Settings $settings -Force | Out-Null
Start-ScheduledTask -TaskName 'CLARA Demo Watchdog'
Write-Host 'CLARA Demo Watchdog installed and started. Logs: .clara/deployment/watchdog.log'
if ($KeepAwakeOnAC) { Write-Host 'Plugged-in idle sleep, hibernation and lid-close sleep disabled. Battery and display settings preserved.' }
