param([ValidateSet('toggle','hide','status')][string]$Command='toggle')
$ErrorActionPreference='Stop'
$config = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'runtime.json') -Raw | ConvertFrom-Json
$client = [IO.Pipes.NamedPipeClientStream]::new('.', $config.pipe, [IO.Pipes.PipeDirection]::InOut, [IO.Pipes.PipeOptions]::Asynchronous)
try {
    $client.Connect(350)
    $encoding = [Text.UTF8Encoding]::new($false)
    $writer = [IO.StreamWriter]::new($client,$encoding,1024,$true)
    $reply = if($Command -eq 'status'){'true'}else{'false'}
    $writer.WriteLine('{"command":"'+$Command+'","reply":'+$reply+'}')
    $writer.Flush()
    if ($Command -eq 'status') {
        $reader = [IO.StreamReader]::new($client,$encoding,$false,1024,$true)
        $task = $reader.ReadLineAsync()
        if ($task.Wait(2000)) { Write-Output $task.Result }
    }
} catch [TimeoutException] {
    if ($Command -eq 'toggle') {
        Start-Process -FilePath $config.python -ArgumentList ('"'+$config.script+'" --toggle') -WorkingDirectory $PSScriptRoot -WindowStyle Hidden | Out-Null
    }
} finally { $client.Dispose() }
