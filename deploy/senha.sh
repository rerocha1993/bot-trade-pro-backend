#!/usr/bin/env bash
# Abre o painel do Conselho BTC na internet com HTTPS e usuário/senha, ou troca a senha.
#
#   sudo bash /opt/conselho/deploy/senha.sh
#
# Pede o usuário e a senha aqui no servidor (a senha não aparece enquanto você digita e não fica salva em texto:
# o Caddy guarda só o hash). O endereço é https://<IP-com-tracos>.sslip.io/painel/ — o sslip.io transforma o IP num
# nome, para o Let's Encrypt emitir o certificado sem você comprar domínio.
set -euo pipefail

DESTINO=/opt/conselho
if [[ $EUID -ne 0 ]]; then echo "rode com sudo: sudo bash $0"; exit 1; fi

IP_PUBLICO="$(curl -4 -s https://api.ipify.org)"
SITE="$(echo "$IP_PUBLICO" | tr '.' '-').sslip.io"
read -r -p "   usuário do painel [conselho]: " USR
USR="${USR:-conselho}"
while true; do
  read -r -s -p "   senha do painel (mínimo 10 caracteres): " SENHA; echo
  [[ ${#SENHA} -ge 10 ]] || { echo "   senha curta demais"; continue; }
  read -r -s -p "   repita a senha: " SENHA2; echo
  [[ "$SENHA" == "$SENHA2" ]] && break
  echo "   as duas não batem, de novo"
done
HASH="$(caddy hash-password --plaintext "$SENHA")"
unset SENHA SENHA2
sed -e "s|__SITE__|$SITE|" -e "s|__USUARIO__|$USR|" -e "s|__HASH__|$HASH|" "$DESTINO/deploy/Caddyfile.modelo" > /etc/caddy/Caddyfile
systemctl reload caddy || systemctl restart caddy

echo
echo " Painel aberto: https://$SITE/painel/"
echo " Usuário: $USR (a senha é a que você digitou). O certificado HTTPS sai no primeiro acesso."
