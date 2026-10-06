param([ValidateSet('Stop','Start')][string]$Action='Stop')
$ErrorActionPreference='Stop'
$name='YASB Stable V1 Watchdog'
$task=Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
$updateData=Join-Path (Split-Path -Parent $PSScriptRoot) 'shell-updater\data'
New-Item -ItemType Directory -Force -Path $updateData | Out-Null
$manual=Join-Path $updateData 'manual-maintenance.json'
if ($Action -eq 'Stop') { '{"manual":true}' | Set-Content -LiteralPath $manual }
else { Remove-Item -LiteralPath $manual -ErrorAction SilentlyContinue }
if (-not $task) {
    New-Item -ItemType Directory -Force -Path $updateData | Out-Null
    $manual=Join-Path $updateData 'manual-maintenance.json'
    if ($Action -eq 'Stop') { '{"manual":true}' | Set-Content -LiteralPath $manual; Write-Output 'Watchdog recovery paused.' }
    else {
        Remove-Item -LiteralPath $manual -ErrorAction SilentlyContinue
        & (Join-Path $PSScriptRoot 'yasb-watchdog.ps1')
        Write-Output 'Watchdog recovery resumed.'
    }
    exit
}
if ($Action -eq 'Stop') {
    Disable-ScheduledTask -TaskName $name | Out-Null
    Stop-ScheduledTask -TaskName $name
    Write-Output 'Watchdog disabled and stopped. YASB/LHM/Time Center/Weather Center can now be closed intentionally. Companion quit: time-center\.venv\Scripts\python.exe weather-center\app\main.py --quit (or time-center\app\main.py --quit).'
} else {
    Enable-ScheduledTask -TaskName $name | Out-Null
    Start-ScheduledTask -TaskName $name
    Write-Output 'Watchdog enabled and started; missing apps recover after its startup grace period.'
}
