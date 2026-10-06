Option Explicit
Dim shell, files, root, python, script, config, line, home
Set shell = CreateObject("WScript.Shell")
Set files = CreateObject("Scripting.FileSystemObject")
root = files.GetParentFolderName(WScript.ScriptFullName)
Set config = files.OpenTextFile(files.BuildPath(root, ".venv\pyvenv.cfg"), 1)
Do Until config.AtEndOfStream
    line = config.ReadLine
    If Left(line, 7) = "home = " Then home = Mid(line, 8)
Loop
config.Close
python = files.BuildPath(home, "pythonw.exe")
script = files.BuildPath(root, "app\main.py")
shell.Run """" & python & """ """ & script & """ --toggle", 0, False
