$ErrorActionPreference='Stop'
$vswherePath='C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe'
$installPath=& $vswherePath -latest -products '*' -property installationPath
if(-not $installPath){throw 'Install Visual Studio C++ build tools to rebuild the optional launcher.'}
$bootstrap=Join-Path $installPath 'VC\Auxiliary\Build\vcvars64.bat'
Push-Location -LiteralPath $PSScriptRoot
try {
    & cmd.exe /d /c ('call "'+$bootstrap+'" >nul && cl /nologo /O2 /MT /EHsc /W4 /DUNICODE /D_UNICODE Launcher.cpp /Fe:Launcher.exe /link /SUBSYSTEM:WINDOWS')
    if($LASTEXITCODE -ne 0){throw 'Launcher build failed; toggle.vbs retains the PowerShell fallback.'}
    $objectPath=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot 'Launcher.obj'))
    if([IO.Path]::GetDirectoryName($objectPath) -ne [IO.Path]::GetFullPath($PSScriptRoot)){throw 'Object path escaped Weather Center.'}
    Remove-Item -LiteralPath $objectPath -ErrorAction SilentlyContinue
} finally { Pop-Location }
