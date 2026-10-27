# Fase 2 — gráfico de verdade, TPO no gráfico e nuvens certas

Pedido do usuário em 27/10/2026. Cada etapa termina com algo que dá para ver no painel.

## Qual "TradingView"

| Opção | O que é | Serve? |
|---|---|---|
| **lightweight-charts** (a que o painel já usa, atualizada para a v5) | biblioteca de código aberto **da própria TradingView**, mesmo visual; aceita desenho nosso (plugins) | **sim — recomendada**: TPO, junção de sessões e nuvens desenhados dentro do gráfico |
| Advanced Charts (charting_library) | o gráfico completo do site da TradingView, hospedado por nós | não: grátis só em site público, sem senha e não pessoal; o painel é privado |
| Widget em iframe | o gráfico do site da TradingView embutido | não: mostra qualquer moeda, mas não deixa desenhar TPO nem nuvem por cima |

## Etapas

1. **Tela Gráfico** — seletor de corretora e par (Coinbase, Binance, Bybit, OKX; à vista e perpétuo), tempos 1m a 1D,
   histórico carregando ao arrastar para a esquerda, tema escuro igual ao da TradingView. Backend:
   `/api/grafico/velas?simbolo=COINBASE:BTC-USD&tempo=30m` com cache por dia.
2. **Botão TPO (30 min)** — em qualquer ativo: perfil de cada sessão desenhado no gráfico, POC, VAH e VAL, e as linhas
   seguindo para a direita até o preço tocar (POC virgem fica aberto).
3. **Juntar sessões com o mouse** — clicar num dia e Shift+clique noutro (ou arrastar): o composto dessas sessões aparece
   com POC/VAH/VAL próprios; dá para juntar quantas quiser e limpar.
4. **Nuvens certas, só em COINBASE:BTC-USD** — o heatmap passa a ser desenhado dentro do gráfico (não numa imagem à parte),
   com a regra do Order Book Depth Overlay do TRDR, e é conferido lado a lado com o TRDR no mesmo horário. Padrão: livro
   da Coinbase (o mesmo do gráfico); opção de somar a Binance à vista, como o TRDR em "Spot".
5. **Painéis de baixo por ativo** — liquidações, funding e saldo do livro onde houver dado público; nos outros ativos,
   sem nuvem.

Telegram: `deploy/telegram.sh` no servidor (o usuário cria o bot no @BotFather e cola o token).

## Quem faz

Especialistas novos em `.claude/agents/`: `arquiteto-plataforma`, `engenheiro-graficos`, `engenheiro-dados-mercado`,
`analista-dados-quant` — junto com o `especialista-tpo` e o `especialista-fluxo` que já existiam.
