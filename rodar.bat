@echo off
REM Sobe o conselho de avisos de BTC: o coletor do livro (janela propria) e a API com o painel.
REM Nao envia ordens: so le dados publicos e avisa. Deixe as duas janelas abertas.
REM Nao consome tokens de IA: sao processos Python falando com APIs publicas.

cd /d "%~dp0"
title Conselho BTC - NAO FECHE ESTA JANELA

echo.
echo  Conselho de avisos BTC
echo  ----------------------
echo  Painel:  http://localhost:8000/painel/
echo  API:     http://localhost:8000/docs
echo  Log:     logs\servidor.log
echo.
echo  O coletor do livro (nuvens) abre em outra janela. Deixe as duas abertas.
echo  Ctrl+C aqui para parar a API.
echo.

start "Coletor do livro" coletor_livro.bat

.venv\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000

echo.
echo  API encerrada.
pause
