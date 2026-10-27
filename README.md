# Conselho de avisos BTC

Sistema de **avisos** para BTC, não de robô: ele nunca envia ordem. Lê dados públicos (Bybit, Binance, Coinbase),
monta o mapa do dia pelo TPO, desenha as "nuvens" do livro de ordens agregado e avisa pelo painel e pelo Telegram.

O sistema de robôs antigo foi substituído por este em 20/10/2026. O código dele está no histórico do git até o
commit `017692d7`.

## No servidor (desde 27/10/2026)

Roda numa VPS (Hostinger KVM 1, Brasil): painel em **https://187-41-98-179.sslip.io/painel/** (usuário `conselho`,
senha definida com `deploy/senha.sh`). Serviços `conselho-coletor`, `conselho-api` e `caddy`; o preenchimento dos
negócios roda todo dia às 03:30 UTC. Para atualizar: `deploy\empacotar.ps1`, `scp` e `deploy/instalar.sh` (passo a
passo em `deploy/LEIAME.md`). Não deixe o PC rodando junto: os robôs ficariam em dobro.

## Instalar no PC (liga sozinho com o Windows)

Dois cliques em **`instalar_windows.bat`**. Ele cria 4 tarefas no Agendador de Tarefas (nome começando com
`ConselhoBTC`): coletor, API com os robôs em simulação, túnel do celular (ngrok) e o preenchimento diário dos negócios
(06:30 e ao entrar no Windows). Tudo roda **sem janela** e cada parte **religa sozinha** 15 s depois de cair
(`windows\manter_rodando.vbs`; quedas em `logs\vigia.log`). Cria o atalho **Conselho BTC** na área de trabalho.

| Para | Faça |
|---|---|
| ver se está tudo rodando e o link do celular | `status_windows.bat` |
| parar tudo agora (volta no próximo login) | `powershell -File windows\parar.ps1` |
| tirar do início do Windows | `desinstalar_windows.bat` (não apaga os dados) |
| link do celular fixo | pegue o domínio grátis em dashboard.ngrok.com → Domains, escreva em `windows\dominio_ngrok.txt` e rode o instalador de novo |

O PC precisa ficar ligado e acordado (suspensão em "Nunca"): com ele desligado o livro daquele período se perde (os
negócios o preenchimento recupera). Depois de atualizar o código, rode `instalar_windows.bat` de novo para religar.

## Como rodar à mão

```bash
# dependências (Python 3.12/3.13, venv em .venv)
.venv\Scripts\python -m pip install -r requirements.txt

# tudo de uma vez: coletor do livro numa janela, API + painel na outra
rodar.bat
#   painel: http://localhost:8000/painel/    API: http://localhost:8000/docs

# só o coletor do livro (grava dados/livro/<exchange>/<dia>.jsonl.gz a cada 30 s)
coletor_livro.bat

# testes e painel
.venv\Scripts\python -m pytest tests -q
cd frontend && npm run build
```

Variáveis do `.env` (ver `.env.exemplo`): `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID` para receber os avisos no
celular; `SERVICO_AVISOS=0` desliga o serviço de avisos.

## Organização

| Onde | O quê |
|---|---|
| `conselho/tpo.py` | TPO por sessão (dia UTC em blocos de 30 min, Ásia/Europa/América, merge, naked POCs) |
| `conselho/composto.py` | composto de ~10 dias: VAL/VAH/POC do range |
| `conselho/mapa_do_dia.py`, `conselho/avisos.py`, `conselho/servico_avisos.py` | mapa do dia e avisos de proximidade, sem probabilidade |
| `conselho/coletor_livro.py`, `conselho/livro_historico.py` | coletor do livro e as nuvens no formato do TRDR |
| `conselho/elliott/` | motor de contagens de Elliott e superciclo (mapa, não gatilho) |
| `conselho/mercado.py` | candles e preço públicos da Bybit, sem chave |
| `conselho/regua.py`, `conselho/estrutura.py` | régua de custo/R e detector de swing, BOS, FVG e CHoCH dos estudos |
| `api/` | rotas `/api/avisos`, `/api/nuvens`, `/api/mercado` e o painel em `/painel` |
| `frontend/` | painel: Mapa e avisos, Nuvens |
| `scripts/estudo_*.py` | estudos com controle sorteado; resumos em `data/estudo_*_resumo.md` |
| `scripts/baixar_historico.py`, `baixar_derivativos.py`, `cenarios_historicos.py` | dados históricos |
| `.claude/agents/especialista-*.md` | os 10 especialistas do conselho |
| `docs/especialistas/` | propostas, plano de gestão e a recomendação final |

## O que foi medido

Cada estratégia é medida com custo real, três períodos (treino 2020–23, validação 2024–jun/25, holdout
jul/25–set/26) e um controle sorteado. Até 20/10/2026, nenhuma passou. A síntese está em
`docs/especialistas/RECOMENDACAO.md`; por isso todo aviso sai marcado "sem % medido".
