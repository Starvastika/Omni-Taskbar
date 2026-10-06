# Optional trusted Authenticode hook. No PFX/token is stored in the repository.
param([Parameter(Mandatory=$true)][string[]]$Paths,[Parameter(Mandatory=$true)][string]$CertificateThumbprint,[string]$TimestampURL='http://timestamp.digicert.com')
$ErrorActionPreference='Stop'
$certificate=Get-Item -LiteralPath ('Cert:\CurrentUser\My\'+$CertificateThumbprint)
if(-not $certificate.HasPrivateKey -or $certificate.NotAfter -le (Get-Date)){throw 'A current trusted code-signing certificate with a private key is required.'}
if(-not ($certificate.EnhancedKeyUsageList | Where-Object {$_.ObjectId -eq '1.3.6.1.5.5.7.3.3'})){throw 'Certificate does not permit code signing.'}
$tool=(Get-Command signtool.exe -ErrorAction Stop).Source
foreach($path in $Paths){
    & $tool sign /sha1 $CertificateThumbprint /fd SHA256 /tr $TimestampURL /td SHA256 /d 'Omni Taskbar' $path
    if($LASTEXITCODE){throw 'Authenticode signing failed.'}
    if((Get-AuthenticodeSignature -LiteralPath $path).Status -ne 'Valid'){throw 'Signature is not trusted; release blocked.'}
}
# Sign launchers BEFORE image inventories/package generation; sign setup AFTER compilation.
# Recompute SHA256SUMS after signing. Configure Inno's SignTool for a signed uninstaller.
