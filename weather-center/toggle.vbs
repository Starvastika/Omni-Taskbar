Option Explicit
Dim shell, files, root, script
Set shell = CreateObject("WScript.Shell")
Set files = CreateObject("Scripting.FileSystemObject")
root = files.GetParentFolderName(WScript.ScriptFullName)
If files.FileExists(files.BuildPath(files.GetParentFolderName(root), "Omni-Taskbar.exe")) Then
    shell.Run """" & files.BuildPath(files.GetParentFolderName(root), "Omni-Taskbar.exe") & """ --weather", 0, False
    WScript.Quit
End If
script = files.BuildPath(root, "Launcher.exe")
If files.FileExists(script) Then
    shell.Run """" & script & """", 0, False
Else
    script = files.BuildPath(root, "toggle.ps1")
    shell.Run "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & script & """", 0, False
End If
