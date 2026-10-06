$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$runtime=Join-Path $root '.runtime\yasb-2.0.7'
$run='HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
$user=[Security.Principal.WindowsIdentity]::GetCurrent().Name
$script=Join-Path $root 'helpers\yasb-watchdog.ps1'
$action=New-ScheduledTaskAction -Execute 'powershell.exe' -Argument ('-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "'+$script+'"') -WorkingDirectory $root
$trigger=New-ScheduledTaskTrigger -AtLogOn -User $user
$principal=New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
$settings=New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
try {
    Register-ScheduledTask -TaskName 'YASB Stable V1 Watchdog' -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
    Start-ScheduledTask -TaskName 'YASB Stable V1 Watchdog'
} catch {
    # Same script/mutex, not another watchdog. HKCU fallback needs no elevation.
    New-ItemProperty -Path $run -Name 'YASB Shell Watchdog' -PropertyType String -Value ('powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "'+$script+'"') -Force | Out-Null
    Start-Process powershell.exe -ArgumentList @('-NoProfile','-WindowStyle','Hidden','-ExecutionPolicy','Bypass','-File',('"'+$script+'"')) -WindowStyle Hidden
}
New-ItemProperty -Path $run -Name YASB -PropertyType String -Value ('"'+(Join-Path $runtime 'yasb.exe')+'"') -Force | Out-Null
