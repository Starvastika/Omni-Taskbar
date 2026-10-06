# Legacy developer bootstrap; not a consumer release asset.
param([string]$Repository='RELEASE_REPOSITORY',[string]$Version='RELEASE_VERSION',[ValidateSet('automatic','check','manual')][string]$UpdateMode,[string]$ReleaseDirectory)
$ErrorActionPreference='Stop'
$root=Join-Path $env:USERPROFILE '.config\yasb'
$scratch=Join-Path ([IO.Path]::GetTempPath()) ('yasb-install-'+[guid]::NewGuid())
New-Item -ItemType Directory -Path $scratch | Out-Null
try {
    if (-not $UpdateMode) {
        Add-Type -AssemblyName System.Windows.Forms
        $form=[Windows.Forms.Form]::new();$form.Text='Taskbar update preference';$form.Width=490;$form.Height=275;$form.StartPosition='CenterScreen'
        $label=[Windows.Forms.Label]::new();$label.Text='Choose how Taskbar Updates should work. You can change this later in the existing ... menu.'
        $label.SetBounds(20,20,435,45);$form.Controls.Add($label)
        $choice=[Windows.Forms.ComboBox]::new();$choice.DropDownStyle='DropDownList';$choice.SetBounds(20,75,435,30)
        $choice.Items.AddRange(@('Automatic updates','Check automatically','Manual only'));$choice.SelectedIndex=1;$form.Controls.Add($choice)
        $help=[Windows.Forms.Label]::new();$help.Text='Automatic stages for the next taskbar restart. Check automatically notifies without installing. Manual only makes no background checks. Windows is never rebooted.'
        $help.SetBounds(20,115,435,60);$form.Controls.Add($help)
        $ok=[Windows.Forms.Button]::new();$ok.Text='Continue';$ok.SetBounds(335,185,120,30);$ok.DialogResult='OK';$form.Controls.Add($ok);$form.AcceptButton=$ok
        if ($form.ShowDialog() -ne 'OK') {throw 'Installation cancelled before modifying the shell.'}
        $UpdateMode=@('automatic','check','manual')[$choice.SelectedIndex];$form.Dispose()
    }
    $python=(Get-Command python.exe -ErrorAction SilentlyContinue).Source
    if (-not $python) {throw 'Install Python 3.14 x64, then run this installer again.'}
    & $python -c 'import sys,struct;assert sys.version_info[:2]==(3,14) and struct.calcsize("P")==8,"Python 3.14 x64 required"'
    if ($LASTEXITCODE) {throw 'Python 3.14 x64 is required.'}
    $python=(& $python -c 'import sys;print(sys.executable)').Trim()
    if ($ReleaseDirectory) {
        $release=(Resolve-Path -LiteralPath $ReleaseDirectory).Path
        Copy-Item -LiteralPath (Join-Path $release 'release-manifest.json') -Destination $scratch
        $manifest=Get-Content -LiteralPath (Join-Path $scratch 'release-manifest.json') -Raw | ConvertFrom-Json
        Copy-Item -LiteralPath (Join-Path $release $manifest.asset) -Destination $scratch
    } else {
        if ($Repository -notmatch '^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$' -or $Version -notmatch '^\d+\.\d+\.\d+$') {throw 'Specify the intended repository and a published stable release version.'}
        $base="https://github.com/$Repository/releases/download/v$Version"
        Invoke-WebRequest -Uri "$base/release-manifest.json" -OutFile (Join-Path $scratch 'release-manifest.json')
        $manifest=Get-Content -LiteralPath (Join-Path $scratch 'release-manifest.json') -Raw | ConvertFrom-Json
        if ($manifest.version -ne $Version -or $manifest.asset -ne "omni-taskbar-$Version-update.zip") {throw 'Release version mismatch.'}
        Invoke-WebRequest -Uri "$base/$($manifest.asset)" -OutFile (Join-Path $scratch $manifest.asset)
    }
    if ($manifest.asset -notmatch '^omni-taskbar-\d+\.\d+\.\d+-update\.zip$' -or $manifest.sha256 -notmatch '^[a-f0-9]{64}$' -or
        (Get-FileHash -LiteralPath (Join-Path $scratch $manifest.asset)).Hash.ToLower() -ne $manifest.sha256) {throw 'Release checksum verification failed.'}
    $extract=Join-Path $scratch 'bootstrap'
    # Execute bootstrap only after SHA-256 verification. Extract only fixed filenames.
    & $python -c 'import sys,zipfile,pathlib;z=zipfile.ZipFile(sys.argv[1]);names=("shell-updater/engine.py","shell-updater/bootstrap.py","shell-updater/native_archive.py");out=pathlib.Path(sys.argv[2]);out.mkdir();[(out/pathlib.Path(n).name).write_bytes(z.read(n)) for n in names]' (Join-Path $scratch $manifest.asset) $extract
    if ($LASTEXITCODE) {throw 'Release bootstrap is incomplete.'}
    & $python (Join-Path $extract 'bootstrap.py') --root $root --archive (Join-Path $scratch $manifest.asset) --manifest (Join-Path $scratch 'release-manifest.json') --mode $UpdateMode
    if ($LASTEXITCODE) {throw 'Installation failed; inspect the actionable message above.'}
} catch {
    Add-Type -AssemblyName System.Windows.Forms
    [Windows.Forms.MessageBox]::Show($_.Exception.Message,'Taskbar installation needs attention','OK','Error') | Out-Null
    exit 1
} finally {
    $resolved=[IO.Path]::GetFullPath($scratch)
    if ($resolved.StartsWith([IO.Path]::GetTempPath(),[StringComparison]::OrdinalIgnoreCase) -and (Split-Path -Leaf $resolved).StartsWith('yasb-install-')) {
        Remove-Item -LiteralPath $resolved -Recurse -Force -ErrorAction SilentlyContinue
    }
}
