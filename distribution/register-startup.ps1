$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$runtime=Join-Path $root '.runtime\yasb-2.0.7'
$run='HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
$user=[Security.Principal.WindowsIdentity]::GetCurrent().Name
$script=Join-Path $root 'shell-updater\watchdog_host.py'
$runtimeSettings=Get-Content -LiteralPath (Join-Path $root 'helpers\runtime-settings.json') -Raw | ConvertFrom-Json
$python=Join-Path ([IO.Path]::GetDirectoryName($runtimeSettings.python)) 'pythonw.exe'
$action=New-ScheduledTaskAction -Execute $python -Argument ('"'+$script+'"') -WorkingDirectory $root
$trigger=New-ScheduledTaskTrigger -AtLogOn -User $user
$principal=New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
$settings=New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -DontStopOnIdleEnd
try {
    Register-ScheduledTask -TaskName 'YASB Stable V1 Watchdog' -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
    Start-ScheduledTask -TaskName 'YASB Stable V1 Watchdog'
} catch {
    # Same script/mutex, not another watchdog. HKCU fallback needs no elevation.
    New-ItemProperty -Path $run -Name 'YASB Shell Watchdog' -PropertyType String -Value ('"'+$python+'" "'+$script+'"') -Force | Out-Null
    Start-Process $python -ArgumentList ('"'+$script+'"') -WindowStyle Hidden
}
New-ItemProperty -Path $run -Name YASB -PropertyType String -Value ('"'+(Join-Path $runtime 'yasb.exe')+'"') -Force | Out-Null
