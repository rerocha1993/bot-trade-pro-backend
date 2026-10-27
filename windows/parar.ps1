# windows\parar.ps1
# Para o Conselho BTC neste PC: as tarefas do Agendador, os vigias e os processos (coletor, API com os robôs, túnel),
# inclusive os que foram abertos à mão pelos arquivos .bat. Não apaga dado nenhum.
$raiz = Split-Path $PSScriptRoot -Parent

Get-ScheduledTask -TaskName 'ConselhoBTC*' -ErrorAction SilentlyContinue | Stop-ScheduledTask -ErrorAction SilentlyContinue

$alvos = 'manter_rodando\.vbs|scripts\\coletor_livro\.py|uvicorn api\.main:app|ngrok(\.exe)?"? +http 127\.0\.0\.1:8000|coletor_livro\.bat|api\.bat|tunel\.bat|rodar\.bat'
# primeiro os vigias (senão eles religam o que for parado), depois o resto
foreach ($rodada in 'vigias', 'processos') {
    Get-CimInstance Win32_Process | Where-Object {
        $_.ProcessId -ne $PID -and $_.CommandLine -and $_.CommandLine -match $alvos -and
        (($rodada -eq 'vigias') -eq ($_.CommandLine -match 'manter_rodando\.vbs'))
    } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
}
Start-Sleep -Seconds 2
Write-Host ' Conselho BTC parado.'
