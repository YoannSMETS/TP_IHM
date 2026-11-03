@echo off
setlocal
cd /d "%~dp0"
if not defined IVY_BUS set "IVY_BUS=127.255.255.255:2010"
sra5.exe -b %IVY_BUS% -g grammaire_parole.grxml -p on