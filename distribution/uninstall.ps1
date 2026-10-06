$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
Disable-ScheduledTask -TaskName 'YASB Stable V1 Watchdog' -ErrorAction SilentlyContinue | Out-Null
Stop-ScheduledTask -TaskName 'YASB Stable V1 Watchdog' -ErrorAction SilentlyContinue
& (Join-Path $root '.runtime\yasb-2.0.7\yasbc.exe') stop
$settings=Get-Content -LiteralPath (Join-Path $root 'helpers\runtime-settings.json') -Raw | ConvertFrom-Json
foreach($name in @('time','weather')) {& $settings.python (Join-Path $root "$name-center\app\main.py") --quit}
Unregister-ScheduledTask -TaskName 'YASB Stable V1 Watchdog' -Confirm:$false -ErrorAction SilentlyContinue
$run='HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
Remove-ItemProperty -LiteralPath $run -Name 'YASB Shell Watchdog' -ErrorAction SilentlyContinue
$updateData=Join-Path $root 'shell-updater\data'
New-Item -ItemType Directory -Force -Path $updateData | Out-Null
'{"manual":true}' | Set-Content -LiteralPath (Join-Path $updateData 'manual-maintenance.json')
$value=(Get-ItemProperty -LiteralPath $run -Name YASB -ErrorAction SilentlyContinue).YASB
if($value -eq ('"'+(Join-Path $root '.runtime\yasb-2.0.7\yasb.exe')+'"')) {Remove-ItemProperty -LiteralPath $run -Name YASB}
Write-Output 'Shell startup removed. User data and stable-v1 retained. Restore Windows taskbar auto-hide through Windows settings if desired.'
