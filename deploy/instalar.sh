#!/usr/bin/env bash
# Instala o Conselho BTC num servidor Ubuntu 22.04/24.04 (Hetzner, Oracle Cloud ou qualquer VPS).
#
#   sudo bash instalar.sh                 # primeira vez: pede a senha do painel
#   sudo bash instalar.sh --atualizar     # depois de enviar um pacote novo: só troca o código e reinicia
#   sudo bash instalar.sh --sem-senha     # instala tudo com o painel fechado; a senha vem depois (deploy/senha.sh)
#
# O que faz:
#   1. instala Python, Caddy (HTTPS automático) e o firewall;
#   2. cria o usuário de sistema "conselho" e copia o código para /opt/conselho;
#   3. cria o ambiente Python com deploy/requirements-servidor.txt;
#   4. cria os serviços conselho-api, conselho-coletor e a rotina diária conselho-negocios (systemd);
#   5. publica o painel em https://<IP-com-tracos>.sslip.io com usuário e senha (o sslip.io transforma o IP num
#      nome, para o Let's Encrypt emitir o certificado sem você comprar domínio).
# Os dados (dados/, data/, logs/) ficam em /opt/conselho e nunca são apagados por uma atualização.
set -euo pipefail

DESTINO=/opt/conselho
USUARIO=conselho
PACOTE_DIR="$(cd "$(dirname "$0")/.." && pwd)"     # a pasta extraída do pacote (contém conselho/, api/, deploy/)
ATUALIZAR=0
SEM_SENHA=0
[[ "${1:-}" == "--atualizar" ]] && ATUALIZAR=1
[[ "${1:-}" == "--sem-senha" ]] && SEM_SENHA=1

if [[ $EUID -ne 0 ]]; then echo "rode com sudo: sudo bash $0"; exit 1; fi

copiar_codigo() {
  mkdir -p "$DESTINO"
  for d in conselho api scripts tests deploy frontend; do
    rm -rf "${DESTINO:?}/$d"
    cp -r "$PACOTE_DIR/$d" "$DESTINO/$d"
  done
  for f in README.md .env.exemplo; do [[ -f "$PACOTE_DIR/$f" ]] && cp "$PACOTE_DIR/$f" "$DESTINO/$f"; done
  mkdir -p "$DESTINO"/{dados,data,logs}
  # dados que vieram no pacote (opcional) entram sem sobrescrever o que já existe no servidor
  for d in dados data; do [[ -d "$PACOTE_DIR/$d" ]] && cp -r --update=none "$PACOTE_DIR/$d/." "$DESTINO/$d/" || true; done
  chown -R "$USUARIO:$USUARIO" "$DESTINO"
}

ambiente_python() {
  sudo -u "$USUARIO" python3 -m venv "$DESTINO/.venv"
  sudo -u "$USUARIO" "$DESTINO/.venv/bin/pip" install -q --upgrade pip
  sudo -u "$USUARIO" "$DESTINO/.venv/bin/pip" install -q -r "$DESTINO/deploy/requirements-servidor.txt"
}

if [[ $ATUALIZAR -eq 1 ]]; then
  echo ">> atualizando o código em $DESTINO"
  copiar_codigo
  ambiente_python
  systemctl restart conselho-coletor conselho-api
  echo ">> pronto. Serviços reiniciados."
  exit 0
fi

echo ">> 1/5 pacotes do sistema"
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q python3 python3-venv python3-pip curl ufw debian-keyring debian-archive-keyring apt-transport-https gnupg
if ! command -v caddy >/dev/null; then
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' > /etc/apt/sources.list.d/caddy-stable.list
  apt-get update -q
  apt-get install -y -q caddy
fi

echo ">> 2/5 usuário e código"
id -u "$USUARIO" >/dev/null 2>&1 || useradd --system --home "$DESTINO" --shell /usr/sbin/nologin "$USUARIO"
copiar_codigo
if [[ ! -f "$DESTINO/.env" ]]; then
  cp "$DESTINO/.env.exemplo" "$DESTINO/.env"
  chown "$USUARIO:$USUARIO" "$DESTINO/.env"
  chmod 600 "$DESTINO/.env"
fi

echo ">> 3/5 ambiente Python (alguns minutos)"
ambiente_python
# roda dentro de $DESTINO: o usuário de sistema não entra em /root, de onde o instalador costuma ser chamado
( cd "$DESTINO" && sudo -u "$USUARIO" "$DESTINO/.venv/bin/python" -m pytest -q -p no:cacheprovider "$DESTINO/tests" | tail -1 ) || echo "   (atenção: algum teste falhou; o resto da instalação segue)"

echo ">> 4/5 serviços"
cp "$DESTINO"/deploy/systemd/*.service "$DESTINO"/deploy/systemd/*.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now conselho-coletor conselho-api conselho-negocios.timer

echo ">> 5/5 painel com HTTPS e senha"
if [[ $SEM_SENHA -eq 1 ]]; then
  echo "   painel ainda FECHADO: rode depois  sudo bash $DESTINO/deploy/senha.sh  para escolher usuário e senha"
else
  bash "$DESTINO/deploy/senha.sh"
fi

ufw allow OpenSSH >/dev/null
ufw allow 80/tcp >/dev/null
ufw allow 443/tcp >/dev/null
ufw --force enable >/dev/null
# imagens Ubuntu da Oracle Cloud trazem iptables próprio que rejeita tudo menos SSH: abre 80 e 443 nele também
if [[ -f /etc/iptables/rules.v4 ]] && grep -q REJECT /etc/iptables/rules.v4; then
  for p in 80 443; do
    iptables -C INPUT -p tcp --dport "$p" -j ACCEPT 2>/dev/null || iptables -I INPUT 5 -p tcp --dport "$p" -j ACCEPT
  done
  command -v netfilter-persistent >/dev/null && netfilter-persistent save >/dev/null || iptables-save > /etc/iptables/rules.v4
fi

echo
echo "================================================================"
echo " Conselho BTC instalado."
echo " Painel:   https://$(curl -4 -s https://api.ipify.org | tr . -).sslip.io/painel/"
echo
echo " Telegram: edite $DESTINO/.env (TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID)"
echo "           e rode: sudo systemctl restart conselho-api"
echo " Logs:     journalctl -u conselho-api -f    |    journalctl -u conselho-coletor -f"
echo " Oracle:   libere as portas 80 e 443 também na Security List da VCN (ver deploy/LEIAME.md)."
echo "================================================================"
