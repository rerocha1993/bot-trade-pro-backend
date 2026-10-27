# windows\desinstalar.ps1  (ou dois cliques em desinstalar_windows.bat)
# Remove o Conselho BTC do início do Windows: para tudo, apaga as tarefas "ConselhoBTC*" e o atalho da área de
# trabalho. Não apaga o projeto nem os dados (dados\, data\, logs\); os .bat continuam funcionando à mão.
& (Join-Path $PSScriptRoot 'parar.ps1') | Out-Null
Get-ScheduledTask -TaskName 'ConselhoBTC*' -ErrorAction SilentlyContinue | Unregister-ScheduledTask -Confirm:$false
$atalho = Join-Path ([Environment]::GetFolderPath('Desktop')) 'Conselho BTC.url'
if (Test-Path $atalho) { Remove-Item $atalho -Force }
Write-Host ''
Write-Host ' Conselho BTC removido do início do Windows. Os dados e o projeto continuam no lugar.'
