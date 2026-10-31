param([switch]$Stop)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
$labRoot = (Get-Location).Path
$labBin = Join-Path $labRoot '.local/portable/pgsql/bin'
$labData = Join-Path $labRoot '.local/pgdata'
if ($Stop) {
    & "$labBin/pg_ctl.exe" -D $labData -m fast stop
    exit $LASTEXITCODE
}
if (-not (Test-Path -LiteralPath "$labBin/postgres.exe")) {
    $labArchive = Join-Path $labRoot '.local/postgresql.zip'
    if (-not (Test-Path -LiteralPath $labArchive)) {
        Invoke-WebRequest -Uri 'https://get.enterprisedb.com/postgresql/postgresql-17.11-5-windows-x64-binaries.zip' -OutFile $labArchive
    }
    & .venv/Scripts/python.exe scripts/extract-postgres.py
    if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL extraction failed' }
}
$labPassword = (Get-Content .env | Where-Object { $_.StartsWith('POSTGRES_PASSWORD=') }).Substring(18)
$labPassword | Set-Content -Encoding ascii .local/pg-password.txt
if (-not (Test-Path -LiteralPath "$labData/PG_VERSION")) {
    & "$labBin/initdb.exe" -D $labData -U lab --auth=scram-sha-256 --pwfile=.local/pg-password.txt --encoding=UTF8 --locale=C
    if ($LASTEXITCODE -ne 0) { throw 'initdb failed' }
}
& "$labBin/pg_ctl.exe" -D $labData status | Out-Null
if ($LASTEXITCODE -ne 0) {
    & "$labBin/pg_ctl.exe" -D $labData -l "$labRoot/.local/postgres.log" -o '-h 127.0.0.1 -p 55432 -c log_min_error_statement=panic' -w start
    if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL startup failed' }
}
$env:PGPASSWORD = $labPassword
foreach ($labDatabase in @('authflow', 'authflow_test')) {
    $exists = & "$labBin/psql.exe" -h 127.0.0.1 -p 55432 -U lab -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$labDatabase'"
    if ($exists -ne '1') {
        & "$labBin/createdb.exe" -h 127.0.0.1 -p 55432 -U lab $labDatabase
        if ($LASTEXITCODE -ne 0) { throw 'Database creation failed' }
    }
}
Remove-Item Env:PGPASSWORD
Write-Output 'Project-local PostgreSQL is ready on 127.0.0.1:55432.'

