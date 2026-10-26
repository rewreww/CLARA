@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop-clara.ps1" %*
set "claraExit=%errorlevel%"
if not "%claraExit%"=="0" pause
exit /b %claraExit%
