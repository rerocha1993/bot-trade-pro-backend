@echo off
REM Preenche os negocios (footprint) que o coletor perdeu quando o PC ficou desligado ou a janela fechou.
REM Bybit: arquivo diario publico (so dias ja fechados). Binance e Coinbase: ultimas 30 horas pelas APIs publicas.
REM O livro de ordens (nuvens) nao tem como ser recuperado: as corretoras nao guardam historico dele.
cd /d "%~dp0"
title Conselho BTC - preenchendo o que faltou
.venv\Scripts\python.exe scripts\baixar_negocios_bybit.py --dias 3
.venv\Scripts\python.exe scripts\preencher_negocios.py --horas 30
echo.
echo  Pronto. Pode fechar esta janela.
pause
