@echo off
rem Usage: launch.bat        -> real speech recognition (sra5)
rem        launch.bat sim    -> speech simulator instead of sra5
setlocal
cd /d "%~dp0"
if not defined IVY_BUS set "IVY_BUS=127.255.255.255:2010"

set "PYTHON=python"
if exist "%~dp0.venv\Scripts\python.exe" set "PYTHON=%~dp0.venv\Scripts\python.exe"
set "PYTHONUNBUFFERED=1"

echo Starting TP_IHM components in this terminal...
start "" /b /d "%~dp0ppilot5_3.3" ppilot5.exe -b %IVY_BUS% -r ppilot5
start "" /b "%PYTHON%" "%~dp0main.py"
start "" /b "%PYTHON%" "%~dp0fusion.py"

if /i "%~1"=="sim" (
    start "" /b "%PYTHON%" "%~dp0speech_simulator.py"
) else (
    start "" /b /d "%~dp0sra5\sra5" sra5.exe -b %IVY_BUS% -g grammaire_parole.grxml -p on
)

echo All components started. Run end.bat to stop them.
