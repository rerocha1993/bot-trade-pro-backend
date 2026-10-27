@echo off
REM Remove o Conselho BTC do inicio do Windows (nao apaga os dados).
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0windows\desinstalar.ps1"
echo.
pause
