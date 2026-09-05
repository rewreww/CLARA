$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$notifierProject = Join-Path $repoRoot "tools\CLARA.Notifier\CLARA.Notifier.csproj"
$notifierExe = Join-Path $repoRoot "tools\CLARA.Notifier\bin\Debug\net8.0-windows10.0.17763.0\win-x64\CLARA.Notifier.exe"
$iconPath = Join-Path $repoRoot "backend\Assets\clara-notification.ico"

dotnet build $notifierProject | Out-Host

if (-not (Test-Path -LiteralPath $notifierExe)) {
    throw "CLARA notifier executable was not created: $notifierExe"
}

& $notifierExe `
    --title "CLARA notifications ready" `
    --body "Windows desktop notifications are registered for CLARA." `
    --level "success" `
    --duration 7000 `
    --icon $iconPath

Write-Host "Registered CLARA Windows App SDK notifications."
Write-Host "Notifier: $notifierExe"
Write-Host "Icon: $iconPath"
