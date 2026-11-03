@echo off
rem Usage: launch.bat        -> real speech recognition (sra5)
rem        launch.bat sim    -> speech simulator instead of sra5
setlocal
cd /d "%~dp0"
if not defined IVY_BUS set "IVY_BUS=127.255.255.255:2010"

start "ppilot5" /d "%~dp0ppilot5_3.3" ppilot5.exe -b %IVY_BUS% -r ppilot5
start "Palette" python main.py
start "Fusion" python fusion.py

if /i "%~1"=="sim" (
    start "Simulateur sra5" python speech_simulator.py
) else (
    start "sra5" /d "%~dp0sra5\sra5" sra5_on.bat
)
