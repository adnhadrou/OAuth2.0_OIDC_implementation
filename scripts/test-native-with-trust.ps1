$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
$labCertPath = (Resolve-Path -LiteralPath '.local/ca.pem').Path
$labCertificate = [System.Security.Cryptography.X509Certificates.X509Certificate2]::new($labCertPath)
$labStorePath = "Cert:\CurrentUser\Root\$($labCertificate.Thumbprint)"
$labAlreadyTrusted = Test-Path -LiteralPath $labStorePath
$labCertificate.Thumbprint | Set-Content .local/test-trust-thumbprint.txt
try {
    if (-not $labAlreadyTrusted) {
        Import-Certificate -FilePath $labCertPath -CertStoreLocation Cert:\CurrentUser\Root | Out-Null
    }
    & .venv/Scripts/python.exe scripts/native-https-tests.py
    $labTestExit = $LASTEXITCODE
} finally {
    if (-not $labAlreadyTrusted -and (Test-Path -LiteralPath $labStorePath)) {
        & certutil -user -f -delstore Root $labCertificate.Thumbprint | Out-Null
        if ($LASTEXITCODE -ne 0 -or (Test-Path -LiteralPath $labStorePath)) {
            throw 'Temporary lab CA cleanup failed; remove the thumbprint in .local/test-trust-thumbprint.txt'
        }
    }
}
exit $labTestExit
