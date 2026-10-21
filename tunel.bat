@echo off
REM Abre o painel no celular por um tunel do ngrok (endereco muda a cada vez que reinicia).
REM O endereco aparece em http://127.0.0.1:4040 ou nas linhas "url=" abaixo.
title Conselho BTC - tunel do celular
ngrok http 127.0.0.1:8000 --log stdout
