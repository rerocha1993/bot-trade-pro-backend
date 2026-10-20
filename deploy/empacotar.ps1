# Gera conselho.tar.gz com o que o servidor precisa (sem .venv, sem node_modules, sem .env).
#
#   powershell -ExecutionPolicy Bypass -File deploy\empacotar.ps1              # código + painel compilado
#   powershell -ExecutionPolicy Bypass -File deploy\empacotar.ps1 -ComDados    # leva também o histórico do livro e dos negócios
#
# Depois: scp conselho.tar.gz root@IP:/root/  e siga o deploy\LEIAME.md.
param([switch]$ComDados)
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
if ($ComDados) {
  New-Item -ItemType Directory -Force "$dst\dados" | Out-Null
  foreach ($d in 'livro', 'negocios') { if (Test-Path "dados\$d") { Copy-Item -Recurse "dados\$d" "$dst\dados\$d" } }
}

$saida = Join-Path $raiz 'conselho.tar.gz'
if (Test-Path $saida) { Remove-Item $saida }
tar -czf $saida -C $tmp conselho_pacote
Remove-Item -Recurse -Force $tmp
$mb = [math]::Round((Get-Item $saida).Length / 1MB, 1)
Write-Host "pacote pronto: $saida ($mb MB)"
