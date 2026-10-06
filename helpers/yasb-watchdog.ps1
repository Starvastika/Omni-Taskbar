# Compatibility entry point; the existing task hosts this same watchdog in pythonw.
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$runtime=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'runtime-settings.json') -Raw | ConvertFrom-Json
$python=Join-Path ([IO.Path]::GetDirectoryName($runtime.python)) 'pythonw.exe'
$script=Join-Path $root 'shell-updater\watchdog_host.py'
Start-Process -FilePath $python -ArgumentList ('"'+$script+'"') -WorkingDirectory $root -WindowStyle Hidden | Out-Null
