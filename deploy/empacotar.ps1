# Gera conselho.tar.gz com o que o servidor precisa (sem .venv, sem node_modules, sem .env).
#
#   powershell -ExecutionPolicy Bypass -File deploy\empacotar.ps1              # código + painel compilado
#   powershell -ExecutionPolicy Bypass -File deploy\empacotar.ps1 -ComDados    # leva também o histórico do livro e dos negócios
#
# Depois: scp conselho.tar.gz root@IP:/root/  e siga o deploy\LEIAME.md.
param([switch]$ComDados, [int]$DiasNegocios = 14)
$ErrorActionPreference = 'Stop'
$raiz = Split-Path -Parent $PSScriptRoot
Set-Location $raiz

# o painel vai compilado (frontend/dist); o servidor não precisa de Node
Push-Location frontend
npm run build | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'npm run build falhou' }
Pop-Location

$tmp = Join-Path $env:TEMP 'conselho_pacote'
if (Test-Path $tmp) { Remove-Item -Recurse -Force $tmp }
New-Item -ItemType Directory -Force "$tmp\conselho_pacote\frontend" | Out-Null
$dst = "$tmp\conselho_pacote"
foreach ($d in 'conselho', 'api', 'scripts', 'tests', 'deploy') { Copy-Item -Recurse $d "$dst\$d" }
Copy-Item -Recurse 'frontend\dist' "$dst\frontend\dist"
Copy-Item 'README.md', '.env.exemplo' $dst
Get-ChildItem -Recurse -Directory -Filter '__pycache__' $dst | Remove-Item -Recurse -Force
# a carteira do Tradeiros (conselho/servico_carteira.py) precisa do histórico longo: diário e 4 h da Binance, diário da
# Bitstamp desde 2011 (graus maiores de Elliott e o topo histórico) e os derivativos; vai junto o resultado do backtest
New-Item -ItemType Directory -Force "$dst\data\historico" | Out-Null
foreach ($f in 'BTCUSDT_binance_1d.csv', 'BTCUSDT_binance_4h.csv', 'BTCUSD_bitstamp_1d.csv', 'fear_greed.csv',
               'funding_bybit.json', 'oi_bybit_1h.json', 'lsr_bybit_1h.json') {
  if (Test-Path "data\historico\$f") { Copy-Item "data\historico\$f" "$dst\data\historico\$f" }
}
if (Test-Path 'data\estudo_tradeiros.json') { Copy-Item 'data\estudo_tradeiros.json' "$dst\data\estudo_tradeiros.json" }

if ($ComDados) {
  # o livro, o livro dos perpétuos e as liquidações inteiros (pequenos e impossíveis de baixar de novo); dos negócios,
  # só os últimos $DiasNegocios dias (o histórico de 2020 em diante é dos estudos, não do painel); e o estado e os
  # trades dos robôs e os avisos, para a simulação continuar de onde está
  New-Item -ItemType Directory -Force "$dst\dados", "$dst\data" | Out-Null
  foreach ($d in 'livro', 'livro_perp', 'liquidacoes') { if (Test-Path "dados\$d") { Copy-Item -Recurse "dados\$d" "$dst\dados\$d" } }
  $corte = (Get-Date).ToUniversalTime().AddDays(-$DiasNegocios).ToString('yyyy-MM-dd')
  Get-ChildItem 'dados\negocios' -Recurse -File -Filter '*.jsonl.gz' | Where-Object { $_.BaseName.Substring(0, 10) -ge $corte } | ForEach-Object {
    $rel = $_.FullName.Substring((Resolve-Path 'dados').Path.Length + 1)
    New-Item -ItemType Directory -Force (Split-Path "$dst\dados\$rel") | Out-Null
    Copy-Item $_.FullName "$dst\dados\$rel"
  }
  if (Test-Path 'data\robos') { Copy-Item -Recurse 'data\robos' "$dst\data\robos" }
  if (Test-Path 'data\avisos.jsonl') { Copy-Item 'data\avisos.jsonl' "$dst\data\avisos.jsonl" }
}

$saida = Join-Path $raiz 'conselho.tar.gz'
if (Test-Path $saida) { Remove-Item $saida }
tar -czf $saida -C $tmp conselho_pacote
Remove-Item -Recurse -Force $tmp
$mb = [math]::Round((Get-Item $saida).Length / 1MB, 1)
Write-Host "pacote pronto: $saida ($mb MB)"
