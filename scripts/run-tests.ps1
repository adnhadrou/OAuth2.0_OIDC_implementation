$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
$credentialLine = Get-Content -LiteralPath .env | Where-Object { $_.StartsWith('POSTGRES_PASSWORD=') }
$labPassword = $credentialLine.Substring('POSTGRES_PASSWORD='.Length)
$env:TEST_DATABASE_URL = "postgresql+psycopg://lab:${labPassword}@127.0.0.1:55432/authflow_test"
& .venv/Scripts/python.exe -m pytest -q -m 'not browser' --tb=short --junitxml=test-results/local.xml
exit $LASTEXITCODE

