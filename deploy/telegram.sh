#!/usr/bin/env bash
# Liga os avisos do Conselho BTC no Telegram (ou troca o bot).
#
#   sudo bash /opt/conselho/deploy/telegram.sh
#
# Antes: no Telegram, fale com o @BotFather, mande /newbot, escolha um nome e um usuário terminado em "bot" e copie o
# token que ele devolve (algo como 123456789:AA...). Aqui você cola o token (não aparece na tela), manda um "oi" para o
# seu bot e o script descobre sozinho o chat, grava no .env, religa a API e manda uma mensagem de teste.
set -euo pipefail

DESTINO=/opt/conselho
if [[ $EUID -ne 0 ]]; then echo "rode com sudo: sudo bash $0"; exit 1; fi

read -r -s -p "   cole o token do @BotFather (não aparece na tela) e Enter: " TOKEN; echo
TOKEN="$(echo -n "$TOKEN" | tr -d '[:space:]')"
export TOKEN ENV_ARQ="$DESTINO/.env"

"$DESTINO/.venv/bin/python" - <<'EOF'
import json, os, re, sys, time, urllib.error, urllib.parse, urllib.request

token = os.environ["TOKEN"]
if not re.fullmatch(r"\d{5,15}:[A-Za-z0-9_-]{30,}", token):
    sys.exit("   isso não parece um token do @BotFather (número, dois-pontos, letras). Rode de novo.")


def api(metodo, **q):
    url = f"https://api.telegram.org/bot{token}/{metodo}"
    dados = urllib.parse.urlencode(q).encode() if q else None
    try:
        return json.load(urllib.request.urlopen(url, data=dados, timeout=40))
    except urllib.error.HTTPError as e:
        return json.load(e)


eu = api("getMe")
if not eu.get("ok"):
    sys.exit("   o Telegram não reconheceu esse token. Confira se copiou inteiro (ou peça outro com /token no @BotFather).")
nome = eu["result"]["username"]
print(f"   bot @{nome} encontrado.")
print(f"   agora, no Telegram, abra https://t.me/{nome} , toque em Iniciar (ou mande \"oi\") — espero até 3 minutos...")

api("deleteWebhook")
chat, ultimo, fim = None, 0, time.time() + 180
while chat is None and time.time() < fim:
    r = api("getUpdates", offset=ultimo + 1, timeout=25)
    for u in r.get("result", []):
        ultimo = max(ultimo, u["update_id"])
        msg = u.get("message") or u.get("my_chat_member") or {}
        if msg.get("chat", {}).get("id"):
            chat = msg["chat"]["id"]
if chat is None:
    sys.exit("   não chegou mensagem nenhuma no bot. Mande um \"oi\" para ele e rode de novo.")
print(f"   chat encontrado ({chat}).")

# grava no .env: tira o \r do Windows e troca (ou acrescenta) as duas linhas
arq = os.environ["ENV_ARQ"]
linhas = open(arq, encoding="utf-8").read().replace("\r", "").splitlines() if os.path.exists(arq) else []
novos = {"TELEGRAM_BOT_TOKEN": token, "TELEGRAM_CHAT_ID": str(chat)}
saida = []
for l in linhas:
    chave = l.split("=", 1)[0].strip()
    if chave in novos:
        saida.append(f"{chave}={novos.pop(chave)}")
    else:
        saida.append(l)
saida += [f"{k}={v}" for k, v in novos.items()]
open(arq, "w", encoding="utf-8").write("\n".join(saida) + "\n")

ok = api("sendMessage", chat_id=chat, text="Conselho BTC: avisos ligados. Daqui pra frente os avisos do servidor chegam aqui.")
print("   mensagem de teste enviada." if ok.get("ok") else f"   o Telegram recusou o teste: {ok.get('description')}")
EOF

chown conselho:conselho "$DESTINO/.env"
chmod 600 "$DESTINO/.env"
unset TOKEN
systemctl restart conselho-api
echo
echo " Pronto: a API foi religada com o Telegram. Os avisos do mapa e dos robôs chegam no seu bot."
