@echo off
REM Sobe so a API do conselho (painel, avisos e os 4 robos em simulacao), sem o coletor.
REM Para subir tudo junto, use rodar.bat.
cd /d "%~dp0"
title Conselho BTC - API
.venv\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000
