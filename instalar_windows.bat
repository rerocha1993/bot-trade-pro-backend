@echo off
REM Instala o Conselho BTC para ligar sozinho com o Windows (sem janela, religa o que cair).
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0windows\instalar.ps1"
echo.
pause
