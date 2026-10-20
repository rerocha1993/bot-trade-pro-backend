@echo off
REM Coletor do livro de ordens de BTC (Coinbase, Binance, Bybit) - SO LEITURA.
REM Grava um snapshot a cada 30 s em dados\livro\<exchange>\<dia>.jsonl.gz.
REM Deixe esta janela aberta. Ctrl+C ou fechar a janela para parar.
REM Nao envia ordens, nao usa credenciais, nao consome tokens de IA.

cd /d "%~dp0"
title Coletor do livro de ordens - NAO FECHE ESTA JANELA

echo.
echo  Coletor do livro de ordens (BTC)
echo  --------------------------------
echo  Exchanges: Coinbase spot, Binance spot, Bybit linear
echo  Dados:     dados\livro\^<exchange^>\^<dia^>.jsonl.gz
echo  Log:       logs\coletor_livro.log
echo.
echo  Deixe esta janela aberta. Ctrl+C para parar.
echo.

.venv\Scripts\python.exe scripts\coletor_livro.py %*

echo.
echo  Coletor encerrado.
pause
