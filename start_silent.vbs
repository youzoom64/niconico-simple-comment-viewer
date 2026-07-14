Option Explicit

Dim shell
Dim fso
Dim scriptDir
Dim pythonwExe
Dim appPath
Dim command

Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
pythonwExe = fso.BuildPath(scriptDir, ".venv\Scripts\pythonw.exe")

If Not fso.FileExists(pythonwExe) Then
    WScript.Echo "Local Python environment not found. Run setup.cmd first."
    WScript.Quit 1
End If

appPath = fso.BuildPath(scriptDir, "main.py")
command = """" & pythonwExe & """ """ & appPath & """ --entrypoint gui"

shell.CurrentDirectory = scriptDir
shell.Environment("PROCESS")("PYTHONUTF8") = "1"
shell.Environment("PROCESS")("PYTHONIOENCODING") = "utf-8"
shell.Run command, 0, False
