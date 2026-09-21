Option Explicit

Dim shell, fso, root, pythonw, app
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

root = fso.GetParentFolderName(WScript.ScriptFullName)
pythonw = root & "\venv\Scripts\pythonw.exe"
app = root & "\jarvis_app.py"

If Not fso.FileExists(pythonw) Then
    pythonw = "pythonw.exe"
End If

shell.CurrentDirectory = root
shell.Run """" & pythonw & """ """ & app & """", 1, False
