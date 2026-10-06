# Runs unelevated. LHM is launched through its protected, fixed-action task.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$settings = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'watchdog-settings.json') -Raw | ConvertFrom-Json
$session = (Get-Process -Id $PID).SessionId
$sid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$mutex = [Threading.Mutex]::new($false, "Local\YASB-StableV1-$sid")
try { $ownsMutex = $mutex.WaitOne(0) } catch [Threading.AbandonedMutexException] { $ownsMutex = $true }
if (-not $ownsMutex) { $mutex.Dispose(); exit }
$log = Join-Path $PSScriptRoot 'watchdog.log'
function Write-Event([string]$message) {
    try {
        if ((Test-Path -LiteralPath $log) -and (Get-Item -LiteralPath $log).Length -gt 65536) {
            Move-Item -LiteralPath $log -Destination "$log.old" -Force
        }
        Add-Content -LiteralPath $log -Value "$(Get-Date -Format o) $message"
    } catch { } # A log failure must not take down recovery.
}
$states = @(
    @{ Name='yasb'; Next=[datetime]::MinValue; Attempts=0; Seen=$null; Pending=$false },
    @{ Name='LibreHardwareMonitor'; Next=[datetime]::MinValue; Attempts=0; Seen=$null; Pending=$false },
    @{ Name='TimeCenter'; Next=[datetime]::MinValue; Attempts=0; Seen=$null; Pending=$false },
    @{ Name='WeatherCenter'; Next=[datetime]::MinValue; Attempts=0; Seen=$null; Pending=$false }
)
try {
    # Allow existing official logon entries to finish first.
    Start-Sleep -Seconds 15
    while ($true) {
        # The updater owns a bounded lease, not another watchdog. Interrupted
        # transactions recover through a pre-update copy of the updater engine.
        $updateData = Join-Path $root 'shell-updater\data'
        if (Test-Path -LiteralPath (Join-Path $updateData 'manual-maintenance.json')) { Start-Sleep -Seconds 8; continue }
        $maintenance = $false
        try {
            $lease = Get-Content -LiteralPath (Join-Path $updateData 'maintenance.json') -Raw | ConvertFrom-Json
            $owner = Get-Process -Id $lease.owner -ErrorAction SilentlyContinue
            $maintenance = ([DateTimeOffset]::UtcNow.ToUnixTimeSeconds() -lt $lease.expires) -and
                [bool]$owner -and ($owner.StartTime.ToUniversalTime() -le [DateTimeOffset]::FromUnixTimeSeconds([long][Math]::Ceiling($lease.created)).UtcDateTime)
        } catch { }
        if ($maintenance) { Start-Sleep -Seconds 8; continue }
        try {
            $updateState = $null
            if (Test-Path -LiteralPath (Join-Path $updateData 'state.json')) {
                $updateState = Get-Content -LiteralPath (Join-Path $updateData 'state.json') -Raw | ConvertFrom-Json
            }
            if ($updateState.transaction) {
                if ($updateState.recovery_attempted) { Start-Sleep -Seconds 8; continue }
                $recovery = Join-Path $updateData 'recovery_runner.py'
                if (Test-Path -LiteralPath $recovery) {
                    $process = Start-Process -FilePath $settings.TimeCenterPython -ArgumentList @(
                        ('"'+$recovery+'"'), '--root', ('"'+$root+'"'), '--action', 'recover'
                    ) -WorkingDirectory $root -WindowStyle Hidden -PassThru
                    $process.WaitForExit(60000) | Out-Null
                    Start-Sleep -Seconds 8
                    continue
                }
            }
        } catch { Write-Event 'Updater recovery needs attention; ordinary recovery remains bounded.' }
        foreach ($state in $states) {
            if ($state.Name -eq 'LibreHardwareMonitor' -and -not $settings.LhmTask) { continue }
            $now = Get-Date
            if ($state.Name -in @('TimeCenter','WeatherCenter')) {
                $running = @()
                try {
                    $companionPython = $settings.($state.Name+'Python')
                    $companionScript = $settings.($state.Name+'Script')
                    $hostInfo = Get-Content -LiteralPath $settings.($state.Name+'Pid') -Raw | ConvertFrom-Json
                    $running = @(Get-Process -Id $hostInfo.pid -ErrorAction SilentlyContinue | Where-Object {
                        $_.SessionId -eq $session -and $_.Path -eq $companionPython -and
                        ($state.Name -ne 'WeatherCenter' -or $hostInfo.script -eq $companionScript) -and
                        [Math]::Abs(($_.StartTime.ToUniversalTime() - [DateTimeOffset]::FromUnixTimeSeconds([long]$hostInfo.started).UtcDateTime).TotalSeconds) -lt 30
                    })
                } catch { }
            } else {
                $running = @(Get-Process -Name $state.Name -ErrorAction SilentlyContinue | Where-Object SessionId -eq $session)
            }
            if ($running.Count -gt 0) {
                if ($state.Pending) { Write-Event "$($state.Name) recovered (PID $($running[0].Id))."; $state.Pending=$false }
                if ($null -eq $state.Seen) { $state.Seen=$now }
                if (($now - $state.Seen).TotalSeconds -ge 30) { $state.Attempts=0 }
                continue
            }
            $state.Seen=$null
            if ($now -lt $state.Next) { continue }
            $state.Attempts++
            $delay = [Math]::Min(300, 30 * [Math]::Pow(2, [Math]::Min(4,$state.Attempts-1)))
            $state.Next=$now.AddSeconds($delay)
            try {
                if ($state.Name -eq 'yasb') {
                    try {
                        $lastUpdate = Get-Content -LiteralPath (Join-Path $updateData 'state.json') -Raw | ConvertFrom-Json
                        if ($state.Attempts -ge 2 -and -not $lastUpdate.failure -and $lastUpdate.last_success -and
                            ([DateTimeOffset]::UtcNow.ToUnixTimeSeconds()-$lastUpdate.last_success.installed_at) -lt 600) {
                            $recovery = Join-Path $updateData 'recovery_runner.py'
                            if (Test-Path -LiteralPath $recovery) {
                                $process = Start-Process -FilePath $settings.TimeCenterPython -ArgumentList @(
                                    ('"'+$recovery+'"'), '--root', ('"'+$root+'"'), '--action', 'post-crash-rollback'
                                ) -WorkingDirectory $root -WindowStyle Hidden -PassThru
                                $process.WaitForExit(60000) | Out-Null
                                Write-Event 'Post-update crash recovery requested.'
                                continue
                            }
                        }
                    } catch { }
                    if (-not (Test-Path -LiteralPath $settings.YasbCli)) { throw 'Verified YASB CLI is missing.' }
                    Start-Process -FilePath $settings.YasbCli -ArgumentList 'start' -WorkingDirectory $root -WindowStyle Hidden | Out-Null
                } elseif ($state.Name -in @('TimeCenter','WeatherCenter')) {
                    $companionPython = $settings.($state.Name+'Python')
                    $companionScript = $settings.($state.Name+'Script')
                    if (-not (Test-Path -LiteralPath $companionPython) -or -not (Test-Path -LiteralPath $companionScript)) { throw "$($state.Name) launcher is missing." }
                    Start-Process -FilePath $companionPython -ArgumentList ('"'+$companionScript+'"') -WorkingDirectory $root -WindowStyle Hidden | Out-Null
                } else {
                    $scheduler = New-Object -ComObject 'Schedule.Service'
                    $scheduler.Connect()
                    $task = $scheduler.GetFolder('\').GetTask($settings.LhmTask)
                    $task.Run($null) | Out-Null
                }
                $state.Pending=$true
                Write-Event "$($state.Name) missing; restart requested (retry delay ${delay}s)."
            } catch {
                Write-Event "$($state.Name) launch failed: $($_.Exception.Message); retry after ${delay}s."
            }
        }
        Start-Sleep -Seconds 8
    }
} finally {
    $mutex.ReleaseMutex()
    $mutex.Dispose()
}
