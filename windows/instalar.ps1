# windows\instalar.ps1  (ou dois cliques em instalar_windows.bat, na pasta do projeto)
#
# Instala o Conselho BTC neste PC para ligar sozinho quando você entra no Windows, sem janela, religando o que cair:
#   1. confere o Python do projeto (.venv) e o painel (frontend\dist); cria o que faltar;
#   2. para o que estiver rodando à mão (janelas dos .bat);
#   3. cria 4 tarefas no Agendador de Tarefas do Windows (nome começando com "ConselhoBTC"):
#        ConselhoBTC - Coletor            livro, negócios, liquidações e livro dos perpétuos
#        ConselhoBTC - API e robos        painel em http://localhost:8000/painel/, avisos e os 4 robôs em SIMULAÇÃO
#        ConselhoBTC - Tunel do celular   ngrok (o link do celular)
#        ConselhoBTC - Preencher          todo dia às 06:30 e ao entrar no Windows: completa os negócios que faltaram
#   4. cria o atalho "Conselho BTC" na área de trabalho e liga tudo agora.
# Não precisa de administrador. Para remover: windows\desinstalar.ps1 (ou desinstalar_windows.bat).
# O PC precisa ficar ligado e acordado (suspensão em "Nunca"): com ele desligado, o livro daquele período se perde.
param([switch]$SemIniciar)
$ErrorActionPreference = 'Stop'
$raiz = Split-Path $PSScriptRoot -Parent
$vbs = Join-Path $PSScriptRoot 'manter_rodando.vbs'
$py = Join-Path $raiz '.venv\Scripts\python.exe'

Write-Host ''
Write-Host ' Conselho BTC - instalação neste PC'
Write-Host ' ----------------------------------'

# 1. Python e painel
if (-not (Test-Path $py)) {
    Write-Host ' >> criando o ambiente Python (.venv), alguns minutos...'
    & py -3 -m venv (Join-Path $raiz '.venv')
    & $py -m pip install -q --upgrade pip
    & $py -m pip install -q -r (Join-Path $raiz 'deploy\requirements-servidor.txt')
}
if (-not (Test-Path (Join-Path $raiz 'frontend\dist\index.html'))) {
    if (Get-Command npm -ErrorAction SilentlyContinue) {
        Write-Host ' >> montando o painel (frontend)...'
        Push-Location (Join-Path $raiz 'frontend')
        try { npm ci --no-audit --no-fund; npm run build } finally { Pop-Location }
    } else {
        Write-Warning 'Node/npm não encontrado e o painel não está montado: a API sobe, mas a tela fica em branco.'
    }
}
if (-not (Get-Command ngrok -ErrorAction SilentlyContinue)) {
    Write-Warning 'ngrok não encontrado: o painel funciona no PC, mas sem o link do celular.'
}

# 2. para o que estiver rodando à mão
& (Join-Path $PSScriptRoot 'parar.ps1') | Out-Null

# 3. tarefas
$usuario = "$env:USERDOMAIN\$env:USERNAME"
$principal = New-ScheduledTaskPrincipal -UserId $usuario -LogonType Interactive -RunLevel Limited
$config = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1)
$aoEntrar = New-ScheduledTaskTrigger -AtLogOn -User $usuario
$tarefas = [ordered]@{
    'ConselhoBTC - Coletor'          = @('coletor',   @($aoEntrar))
    'ConselhoBTC - API e robos'      = @('api',       @($aoEntrar))
    'ConselhoBTC - Tunel do celular' = @('tunel',     @($aoEntrar))
    'ConselhoBTC - Preencher'        = @('preencher', @((New-ScheduledTaskTrigger -Daily -At '06:30'), $aoEntrar))
}
foreach ($nome in $tarefas.Keys) {
    $servico, $gatilhos = $tarefas[$nome]
    $acao = New-ScheduledTaskAction -Execute 'wscript.exe' -Argument "`"$vbs`" $servico" -WorkingDirectory $raiz
    Register-ScheduledTask -TaskName $nome -Action $acao -Trigger $gatilhos -Principal $principal -Settings $config `
        -Description "Conselho BTC ($servico). Instalado por windows\instalar.ps1; remova com windows\desinstalar.ps1." -Force | Out-Null
    Write-Host " >> tarefa criada: $nome"
}

# 4. atalho e início
$atalho = Join-Path ([Environment]::GetFolderPath('Desktop')) 'Conselho BTC.url'
Set-Content -Path $atalho -Value "[InternetShortcut]`r`nURL=http://localhost:8000/painel/`r`n" -Encoding ASCII
Write-Host " >> atalho na área de trabalho: Conselho BTC"

if (-not $SemIniciar) {
    foreach ($nome in 'ConselhoBTC - Coletor', 'ConselhoBTC - API e robos', 'ConselhoBTC - Tunel do celular') {
        Start-ScheduledTask -TaskName $nome
        Start-Sleep -Seconds 3
    }
    Write-Host ' >> ligando (a API leva uns segundos)...'
    $ate = (Get-Date).AddSeconds(90)
    while ((Get-Date) -lt $ate) {
        try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 'http://127.0.0.1:8000/api/robos' | Out-Null; break } catch { Start-Sleep -Seconds 2 }
    }
    & (Join-Path $PSScriptRoot 'status.ps1')
}
Write-Host ''
Write-Host ' Pronto. A partir de agora tudo liga sozinho quando você entra no Windows.'
Write-Host ' Painel: atalho "Conselho BTC" na área de trabalho. Situação e link do celular: status_windows.bat'
