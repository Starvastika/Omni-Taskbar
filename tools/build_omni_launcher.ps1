$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$vswhere='C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe'
$installation=& $vswhere -latest -products '*' -property installationPath
if(-not $installation){throw 'Visual Studio C++ build tools required for developer/CI build only'}
$environment=Join-Path $installation 'VC\Auxiliary\Build\vcvars64.bat'
$source=Join-Path $root 'distribution\Omni-Taskbar.cpp'
$dest=Join-Path $root 'dist\Omni-Taskbar.exe'
New-Item -ItemType Directory -Force -Path (Join-Path $root 'dist') | Out-Null
Push-Location -LiteralPath (Join-Path $root 'dist')
try {
    & cmd.exe /d /c ('call "'+$environment+'" >nul && cl /nologo /std:c++17 /O2 /MT /EHsc /W4 /DUNICODE /D_UNICODE "'+$source+'" /Fe:"'+$dest+'" /link /SUBSYSTEM:WINDOWS user32.lib shell32.lib')
    if($LASTEXITCODE){throw 'Omni launcher build failed'}
} finally {Pop-Location}
