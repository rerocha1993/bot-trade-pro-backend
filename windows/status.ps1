# windows\status.ps1  (ou dois cliques em status_windows.bat)
# Mostra se cada parte do Conselho BTC está rodando, o estado dos robôs e o link do celular.
$raiz = Split-Path $PSScriptRoot -Parent
$procs = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine }
$partes = [ordered]@{
    'Coletor (livro, negócios, liquidações)' = 'scripts\\coletor_livro\.py'
    'API e robôs'                            = 'uvicorn api\.main:app'
    'Túnel do celular (ngrok)'               = 'ngrok(\.exe)?"? +http 127\.0\.0\.1:8000'
}
Write-Host ''
foreach ($p in $partes.Keys) {
    $ok = [bool]($procs | Where-Object { $_.CommandLine -match $partes[$p] })
    Write-Host (' {0,-42} {1}' -f $p, $(if ($ok) { 'rodando' } else { 'PARADO' }))
}
try {
    $r = Invoke-RestMethod -TimeoutSec 5 'http://127.0.0.1:8000/api/robos'
    $erro = if ($r.ultimo_erro) { $r.ultimo_erro } else { 'nenhum' }
    Write-Host (' Robôs: {0}, simulação, {1} ciclos, último erro: {2}' -f $(if ($r.ativo) { 'ligados' } else { 'desligados' }), $r.ciclos, $erro)
} catch { Write-Host ' Robôs: a API não respondeu' }
try {
    $t = Invoke-RestMethod -TimeoutSec 5 'http://127.0.0.1:4040/api/tunnels'
    Write-Host (' Celular: {0}/painel/' -f $t.tunnels[0].public_url)
} catch { Write-Host ' Celular: túnel sem resposta' }
Write-Host ' PC:      http://localhost:8000/painel/'
$tarefas = Get-ScheduledTask -TaskName 'ConselhoBTC*' -ErrorAction SilentlyContinue
if (-not $tarefas) { Write-Host ' Tarefas do Windows: não instaladas (rode instalar_windows.bat)' }
