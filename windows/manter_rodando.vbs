' windows\manter_rodando.vbs <coletor | api | tunel | preencher>
'
' Vigia do Conselho BTC no Windows: roda a parte pedida SEM janela e, se ela cair, espera 15 s e roda de novo,
' para sempre. As tarefas do Agendador criadas por windows\instalar.ps1 chamam este arquivo quando você entra no
' Windows. "preencher" roda uma vez só (a rotina diária que completa os negócios que faltaram).
' Cada queda vai para logs\vigia.log. Não envia ordem nenhuma: só os mesmos processos dos arquivos .bat.
Option Explicit

Dim fso, sh, raiz, servico, cmd, py, dominio, umaVez, codigo, arq
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")
raiz = fso.GetParentFolderName(fso.GetParentFolderName(WScript.ScriptFullName))
sh.CurrentDirectory = raiz
If Not fso.FolderExists(raiz & "\logs") Then fso.CreateFolder(raiz & "\logs")

Sub Registrar(msg)
    ' os vigias ligam juntos e disputam o mesmo arquivo: tenta algumas vezes e, se não der, segue sem registrar
    ' (um erro aqui abriria uma janela invisível do Windows Script Host e travaria o vigia)
    Dim f, tentativa
    On Error Resume Next
    For tentativa = 1 To 10
        Err.Clear
        Set f = fso.OpenTextFile(raiz & "\logs\vigia.log", 8, True)
        If Err.Number = 0 Then
            f.WriteLine Now & "  " & servico & ": " & msg
            f.Close
            Exit For
        End If
        WScript.Sleep 300
    Next
    On Error GoTo 0
End Sub

If WScript.Arguments.Count < 1 Then WScript.Quit 2
servico = LCase(WScript.Arguments(0))
py = """" & raiz & "\.venv\Scripts\python.exe"""
umaVez = False

Select Case servico
    Case "coletor"
        cmd = py & " scripts\coletor_livro.py --silencioso"
    Case "api"
        cmd = py & " -m uvicorn api.main:app --host 127.0.0.1 --port 8000"
    Case "tunel"
        cmd = "ngrok http 127.0.0.1:8000 --log """ & raiz & "\logs\ngrok.log"""
        ' endereço fixo do celular (opcional): o domínio grátis do ngrok, escrito em windows\dominio_ngrok.txt
        If fso.FileExists(raiz & "\windows\dominio_ngrok.txt") Then
            Set arq = fso.OpenTextFile(raiz & "\windows\dominio_ngrok.txt")
            If Not arq.AtEndOfStream Then dominio = Trim(arq.ReadAll)
            arq.Close
            dominio = Replace(Replace(dominio, vbCr, ""), vbLf, "")
            If Len(dominio) > 0 Then cmd = cmd & " --url=" & dominio
        End If
    Case "preencher"
        umaVez = True
    Case Else
        WScript.Quit 2
End Select

If umaVez Then
    Registrar "preenchendo os negocios que faltaram"
    sh.Run "cmd /c """ & py & " scripts\baixar_negocios_bybit.py --dias 3 >> logs\preencher.log 2>&1""", 0, True
    codigo = sh.Run("cmd /c """ & py & " scripts\preencher_negocios.py --horas 30 >> logs\preencher.log 2>&1""", 0, True)
    Registrar "preenchimento terminou (codigo " & codigo & ")"
    WScript.Quit codigo
End If

Registrar "ligando"
Do
    codigo = sh.Run(cmd, 0, True)
    Registrar "parou (codigo " & codigo & "); religo em 15 s"
    WScript.Sleep 15000
Loop
