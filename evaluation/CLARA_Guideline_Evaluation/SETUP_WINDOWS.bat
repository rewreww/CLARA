@echo off
cd /d "%~dp0"
py -3 -m venv .venv
if errorlevel 1 goto fail
.venv\Scripts\python -m pip install -r requirements.txt
if errorlevel 1 goto fail
.venv\Scripts\python -m unittest -v
if errorlevel 1 goto fail
echo Setup and offline tests completed. Read README.md for the next step.
pause
exit /b 0
:fail
echo Setup failed. Keep this window open and share the error text.
pause
exit /b 1
