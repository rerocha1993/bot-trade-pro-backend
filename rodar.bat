@echo off
REM Sobe a API, o painel e TODOS os robos ativos, num processo so.
REM Deixe esta janela aberta. Fechar a janela ou Ctrl+C para os robos.
REM Nao consome tokens de IA: sao processos Python falando com a Bybit.

cd /d "%~dp0"
title Bot Trade Pro - NAO FECHE ESTA JANELA

echo.
echo  Bot Trade Pro
echo  -------------
echo  Painel:  http://localhost:8000/painel/
echo  API:     http://localhost:8000/docs
echo  Log:     logs\servidor.log
echo.
echo  Deixe esta janela aberta. Ctrl+C para parar tudo.
echo.

REM O LocalDB desliga sozinho por ociosidade e demora a subir na primeira conexao.
REM Acordar antes evita o erro "o tempo limite do logon expirou".
echo  Acordando o banco...
sqllocaldb start MSSQLLocalDB >nul 2>&1

.venv\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000

echo.
echo  Servidor encerrado. Os robos pararam.
pause
