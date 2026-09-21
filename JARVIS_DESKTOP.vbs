Option Explicit

Dim shell, fileSystem, root, python
Set shell = CreateObject("WScript.Shell")
Set fileSystem = CreateObject("Scripting.FileSystemObject")
root = fileSystem.GetParentFolderName(WScript.ScriptFullName)
python = root & "\venv\Scripts\pythonw.exe"

If Not fileSystem.FileExists(python) Then
    python = "pythonw.exe"
End If

shell.CurrentDirectory = root
shell.Run """" & python & """ """ & root & "\jarvis_app.py""", 1, False
