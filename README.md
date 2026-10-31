# AuthFlow Lab — OAuth/OIDC Implementation and Security Testing

A local portfolio project for learning how authorization codes, PKCE, browser transactions and token validation fit together. Three Flask services implement an explicit OAuth/OIDC subset. The authorization server's state machine is written here; cryptographic primitives come from maintained libraries.

This is an **educational implementation**, not a production identity provider or a certified OIDC product. Use synthetic users and data. No Azure, Entra ID, external identity service or cloud credentials are required. Nothing is published by the setup commands.

Latest validation: **70 tests passed in Docker on 2026-10-31**, including Chromium, PostgreSQL concurrency and independent-client interoperability. See the [final check and security updates](docs/final-check-2026-10-31.md).

## Start on Windows / PowerShell

Prerequisites: Python 3.14, Git, Docker Desktop with its Linux engine running, and available localhost ports 55432, 8443–8445. Run commands from this directory.

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.lock
.venv/Scripts/python.exe scripts/bootstrap.py
docker compose up -d --build
```

Bootstrap generates new synthetic credentials and keys in ignored `.local/` and a database password in ignored `.env`. It preserves existing credentials on repeat runs. Open `.local/secrets.json` privately to obtain the synthetic `student` password; do not paste that file in an issue, recording or commit. Client credentials are also generated, never copied from another project.

### Manual local HTTPS trust

The certificate covers exactly `auth.authflow.test`, `client.authflow.test` and `api.authflow.test`. Add this line to `C:\Windows\System32\drivers\etc\hosts` using an elevated editor:

```text
127.0.0.1 auth.authflow.test client.authflow.test api.authflow.test
```

Trust **only the generated lab CA** in your current user's Windows root store:

```powershell
$labCertificate = Import-Certificate -FilePath .local/ca.pem -CertStoreLocation Cert:\CurrentUser\Root
$labCertificate.Thumbprint | Set-Content .local/trusted-thumbprint.txt
```

Restart your browser if necessary. Visit **https://client.authflow.test:8444**, start sign-in, enter the synthetic account, consent and read protected notes. Do not bypass certificate warnings. If using Firefox with its own trust store, import `.local/ca.pem` into its authorities or use Edge/Chrome with the Windows trust store.

Requests from containers use the same public hostnames and ports: Docker DNS maps all three names to Caddy. Python requests explicitly verifies `.local/ca.pem`. The browser tests import this CA into Chromium's NSS store inside their isolated container. No `verify=False`, `ignore_https_errors` or TLS bypass flags are used.

To remove trust after the exercise (the thumbprint was recorded above):

```powershell
$labThumbprint = (Get-Content .local/trusted-thumbprint.txt).Trim()
Remove-Item -LiteralPath "Cert:\CurrentUser\Root\$labThumbprint"
```

For a noninteractive run, `scripts/test-native-with-trust.ps1` uses `certutil -user -f -delstore Root` with the exact generated thumbprint in a `finally` block and verifies removal. PowerShell's certificate provider can require a UI prompt.

Remove the three hosts aliases manually. The leaf certificate lasts 90 days. To renew only TLS, stop the services, remove trust for the old CA, run `python scripts/bootstrap.py --renew-tls`, trust the new `.local/ca.pem` and restart. Credentials, database and signing keys are preserved. For a completely fresh lab, stop the stack, back up any wanted results, remove the lab database volume with `docker compose down -v`, remove only this project's `.local/` and `.env`, rerun bootstrap and replace the trusted CA. This deliberately resets all lab accounts, keys and state. Bootstrap does not silently rotate credentials against an existing database.

## Alternative local setups

### Windows fallback when Docker Desktop cannot start

The repository also includes a portable PostgreSQL + native HTTPS runner. It keeps the database/runtime in ignored `.local/`, installs no Windows service and binds all listeners to loopback. Do not run it alongside Compose on the same ports.

```powershell
# Downloads the official EDB PostgreSQL 17.11 portable archive (~382 MB)
./scripts/portable-postgres.ps1
./scripts/run-tests.ps1

# After the same manual CA trust and hosts setup described above
.venv/Scripts/python.exe scripts/native-https-tests.py --serve
# Ctrl+C stops the three HTTPS services
./scripts/portable-postgres.ps1 -Stop
```

The native runner uses Werkzeug's threaded HTTPS server for this local lab only. Its internal requests map the three fixed lab DNS names to loopback while verifying their original hostname/certificate. It does not alter the machine's hosts file. This verifies application behavior but does not validate the Caddy/container deployment.

For native browser tests, install Chromium in the project and run the harness while the generated CA is trusted by the same user's Windows browser store:

```powershell
$env:PLAYWRIGHT_BROWSERS_PATH = (Join-Path (Get-Location).Path '.local/browsers')
.venv/Scripts/python.exe -m playwright install chromium
.venv/Scripts/python.exe scripts/native-https-tests.py
```

### Linux/CI commands

```bash
python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python scripts/bootstrap.py
docker compose up -d --build
docker compose --profile test run --build --rm tests
```

For a human browser on Linux, add the same hosts aliases to `/etc/hosts` and import `.local/ca.pem` into that browser's certificate authorities. On Debian/Ubuntu the system store can be populated with `sudo install -m 644 .local/ca.pem /usr/local/share/ca-certificates/authflow-lab.crt` followed by `sudo update-ca-certificates`. Chromium may additionally need its NSS store: see `scripts/test-entrypoint.sh`. Container tests require neither host aliases nor host trust changes.

## Run checks

```powershell
# Pure token validation and PKCE properties; no Docker needed
.venv/Scripts/python.exe -m pytest tests/test_tokens.py -q

# Real PostgreSQL protocol, client transaction and concurrent redemption tests
./scripts/run-tests.ps1

# Entire suite, real HTTPS Chromium flow and independent Authlib client
docker compose --profile test run --build --rm tests

# Static checks and dependency advisory audit
.venv/Scripts/python.exe -m ruff check .
.venv/Scripts/python.exe -m ruff format --check .
.venv/Scripts/python.exe -m pip_audit -r requirements.lock --progress-spinner off

# Export a shareable report without captured request data or tracebacks
.venv/Scripts/python.exe scripts/report.py test-results/results.xml
```

Linux host integration equivalent (uses only this lab's generated `.env`):

```bash
set -a
. ./.env
set +a
TEST_DATABASE_URL="postgresql+psycopg://lab:${POSTGRES_PASSWORD}@127.0.0.1:55432/authflow_test" \
  .venv/bin/python -m pytest -q -m 'not browser' --tb=short --junitxml=test-results/local.xml
```

Tests reset **only `authflow_test`** and refuse other database names. Without `TEST_DATABASE_URL`, database tests explicitly skip. With a configured but unavailable database, they fail. Do not interpret a token-only green run as a passing integration suite. See [actual results](docs/test-results.md) and the [requirements matrix](docs/requirements-matrix.md).

CI runs lint, formatting, dependency audit and the full Compose test suite on an ephemeral runner. Only sanitized test names/statuses are uploaded; raw JUnit is ignored locally because failed assertions can contain synthetic secrets. CI is supplied, not claimed to have run on GitHub.


## Local operational limits

The database and internal HTTP hops sit on a trusted, single-host Docker network. Public ports bind only to loopback. Services share one database role, which is a documented lab isolation limitation; do not use this deployment for mutually untrusted services. Private signing material is mounted only into the authorization server (and the one-shot migration/test environment). Caddy sees only the TLS key. The client receives only its own client secret. No application endpoint prints tokens or secrets, and access/debug logging is disabled.

`Clear client session` removes the client session; it is not OIDC logout and does not terminate the authorization-server login or revoke all grants. Tokens expire in five minutes. No refresh tokens are implemented. Expired database records are not automatically pruned in this small lab.

```powershell
docker compose stop  # Preserve data for another session
docker compose down # Remove containers; retain the named database volume
```
