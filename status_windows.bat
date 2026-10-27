@echo off
REM Mostra se tudo esta rodando, o estado dos robos e o link do celular.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0windows\status.ps1"
echo.
pause
