Option Explicit

Dim shell
Dim fso
Dim scriptDir
Dim rootDir
Dim niconicoRoot
Dim pythonwExe
Dim appPath
Dim command

Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
rootDir = fso.GetAbsolutePathName(fso.BuildPath(scriptDir, "..\.."))
niconicoRoot = fso.GetAbsolutePathName(fso.BuildPath(scriptDir, ".."))
pythonwExe = ""

If fso.FileExists(fso.BuildPath(scriptDir, ".venv\Scripts\pythonw.exe")) Then
    pythonwExe = fso.BuildPath(scriptDir, ".venv\Scripts\pythonw.exe")
ElseIf fso.FileExists(fso.BuildPath(niconicoRoot, "niconico-watch-app\.venv\Scripts\pythonw.exe")) Then
    pythonwExe = fso.BuildPath(niconicoRoot, "niconico-watch-app\.venv\Scripts\pythonw.exe")
ElseIf fso.FileExists(fso.BuildPath(rootDir, ".venv\Scripts\pythonw.exe")) Then
    pythonwExe = fso.BuildPath(rootDir, ".venv\Scripts\pythonw.exe")
End If

If pythonwExe = "" Then
    WScript.Echo "Niconico venv Python not found: " & fso.BuildPath(niconicoRoot, "niconico-watch-app\.venv\Scripts\pythonw.exe")
    WScript.Quit 1
End If

appPath = fso.BuildPath(scriptDir, "main.py")
command = """" & pythonwExe & """ """ & appPath & """ --entrypoint gui"

shell.CurrentDirectory = scriptDir
shell.Environment("PROCESS")("PYTHONUTF8") = "1"
shell.Environment("PROCESS")("PYTHONIOENCODING") = "utf-8"
shell.Run command, 0, False
