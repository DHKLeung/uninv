@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0run-ibkr-gateway.ps1"
endlocal
