# Publicar o Conselho BTC num servidor barato

O sistema é leve: dois processos Python ligados o tempo todo (o coletor e a API) e uns 5 MB de dados por dia.
Qualquer servidor com 1–2 GB de RAM e Ubuntu 22.04 ou 24.04 serve.

| Opção | Custo | Prós | Contras |
|---|---|---|---|
| **Hetzner Cloud CX22** (Alemanha ou Finlândia) | cerca de € 4/mês | simples, estável, cria em 1 minuto | pago |
| **Oracle Cloud Free Tier** (VM.Standard.A1.Flex, ARM) | grátis | até 4 núcleos e 24 GB sem pagar | pede cartão no cadastro; às vezes falta máquina livre na região; firewall em dois lugares |

Não use região nos Estados Unidos: a Bybit e a Binance bloqueiam IPs de lá. Não use planos grátis que "dormem"
(Render, Railway): o coletor precisa ficar ligado.

---

## 1. Criar o servidor

**Hetzner**
1. Crie a conta em hetzner.com/cloud e um projeto.
2. *Add Server* → localização Falkenstein, Nuremberg ou Helsinki → imagem **Ubuntu 24.04** → tipo **CX22**.
3. Em *SSH keys*, adicione a sua chave pública (no Windows: `ssh-keygen` e depois o conteúdo de
   `C:\Users\<você>\.ssh\id_ed25519.pub`). Crie o servidor e anote o **IP**.

**Oracle Cloud**
1. Crie a conta em cloud.oracle.com (Free Tier) e escolha uma região fora dos EUA (ex.: São Paulo ou Frankfurt).
2. *Compute → Instances → Create* → imagem **Canonical Ubuntu 24.04** → shape **VM.Standard.A1.Flex**
   (1–2 OCPU, 6–12 GB) → adicione a sua chave SSH pública → crie e anote o **IP público**.
3. **Firewall da nuvem**: *Networking → Virtual Cloud Networks → (sua VCN) → Security Lists → Default* →
   *Add Ingress Rules*: origem `0.0.0.0/0`, TCP, portas **80** e **443**. (O firewall de dentro da máquina o
   instalador abre sozinho.)

## 2. Gerar e enviar o pacote (no seu Windows, na pasta do projeto)

```powershell
powershell -ExecutionPolicy Bypass -File deploy\empacotar.ps1
```

Use `-ComDados` para levar também o histórico do livro e dos negócios (fica bem maior). Depois envie:

```powershell
scp conselho.tar.gz root@SEU_IP:/root/
```

Na Oracle o usuário é `ubuntu` em vez de `root` (`scp conselho.tar.gz ubuntu@SEU_IP:~/`).

## 3. Instalar (no servidor)

```bash
ssh root@SEU_IP
tar -xzf conselho.tar.gz
sudo bash conselho_pacote/deploy/instalar.sh
```

O instalador leva alguns minutos, roda os testes e pede **um usuário e uma senha para o painel** (mínimo de 10
caracteres; a senha não aparece enquanto você digita). No fim ele mostra o endereço:

```
Painel:   https://SEU-IP-COM-TRACOS.sslip.io/painel/
```

Abra no celular, digite o usuário e a senha. O certificado HTTPS é emitido sozinho no primeiro acesso.

## 4. Telegram (para os avisos chegarem no celular)

1. No Telegram, fale com o **@BotFather**, mande `/newbot` e copie o token.
2. Mande qualquer mensagem para o seu bot e depois fale com o **@userinfobot** para saber o seu chat_id.
3. No servidor:

```bash
sudo nano /opt/conselho/.env          # preencha TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID
sudo systemctl restart conselho-api
```

## Dia a dia

| Para | Comando no servidor |
|---|---|
| ver se está tudo rodando | `systemctl status conselho-api conselho-coletor` |
| ver o log ao vivo | `journalctl -u conselho-api -f` ou `journalctl -u conselho-coletor -f` |
| atualizar o código | gere e envie um pacote novo, `tar -xzf conselho.tar.gz` e `sudo bash conselho_pacote/deploy/instalar.sh --atualizar` |
| trocar a senha do painel | `caddy hash-password` e troque a linha do usuário em `/etc/caddy/Caddyfile`; depois `sudo systemctl reload caddy` |
| preencher o footprint dos últimos dias | roda sozinho todo dia às 03:30 UTC (`systemctl list-timers conselho-negocios.timer`) |

Os dados ficam em `/opt/conselho/dados` e `/opt/conselho/data`; uma atualização nunca os apaga.

## O que o servidor NÃO faz

Não envia ordem e não guarda chave de corretora: só lê dados públicos e avisa. Por isso o `.env` do servidor
tem só o Telegram.
