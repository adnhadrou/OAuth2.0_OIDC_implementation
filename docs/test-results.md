# Executed checks

## Latest validation — 2026-10-31

The full Linux Docker suite passed: **70 passed, 0 failures, 0 errors, 0 skipped** in 11.787 seconds. This includes both Chromium tests, independent Authlib interoperability, verified HTTPS and concurrent PostgreSQL code redemption. Three dependency security updates were applied and the fresh advisory audit reported no known vulnerabilities. The earlier container-runtime and frontend browser-retest gaps are now resolved. GitHub-hosted Actions remains unexecuted until the repository is published.

See the [final readiness report](final-check-2026-10-31.md) and [sanitized per-case results](final-2026-10-31-tests.md).

## Historical validation — 2026-10-16

**Frontend follow-up:** Docker was running during the later UI revision. `docker compose up -d --build auth client api` succeeded. All six templates rendered without horizontal overflow at 1280px and 375px in Chromium. `docker compose exec -T -e RUN_BROWSER=1 auth python -m pytest tests/test_live.py -q --tb=short -k 'https_requires_trusted_ca or independent_authlib_oidc_client'` reported **2 passed, 2 deselected**. The Windows certificate-store import blocked the full live-browser retest of the updated pages. The original implementation results below are retained as historical evidence; the earlier Docker startup blocker no longer applies to the running deployment, but the complete container test suite was not rerun in this follow-up.

**70 test cases passed across two executions.** The application was exercised locally on Windows with Python 3.14.3, PostgreSQL 17.11 and real HTTPS. No coverage percentage, throughput claim, OIDC certification or CVE is asserted.

| Check | Observed result |
|---|---|
| Host PostgreSQL protocol/security/unit suite | **66 passed**, 4 browser tests deselected; 15.26 seconds reported by pytest |
| Eight-worker concurrent code redemption | **PASS** inside the 66-test run: exactly one 200, seven invalid_grant responses |
| Native HTTPS live suite | **4 passed**, 21.78 seconds reported by pytest |
| Chromium login → consent → callback → API | **PASS**; verified TLS, secure HttpOnly cookies, no tokens in rendered page/localStorage |
| Chromium callback state attack | **PASS** (rejected) |
| Independent Authlib OAuth/OIDC client | **PASS** against real HTTPS endpoints; joserfc signature verification and Authlib ID claims validation |
| Untrusted versus trusted CA | **PASS**; default public roots reject the lab certificate, explicit lab CA succeeds |
| Ruff lint and formatting | **PASS** |
| Python bytecode compilation | **PASS** |
| pip dependency consistency | **PASS**: no broken requirements |
| pip-audit over requirements.lock | **PASS**: no known vulnerabilities found at execution time |
| docker compose config --quiet | **PASS**: configuration parses and resolves |
| Docker image build / Caddy deployment / Linux container tests | **BLOCKED** by Docker Desktop's inference-manager startup failure; not claimed as executed |
| GitHub Actions workflow | Supplied locally; **NOT RUN** on GitHub, repository not published |
| Keycloak comparison, refresh tokens, key rotation | Optional and intentionally not implemented |

The first PostgreSQL command inside the execution sandbox failed with a loopback socket permission error. It was rerun outside that sandbox and passed. The first live run failed strict TLS validation because the generated certificate lacked AKI; the generator was fixed and the final four-test run passed. The successful PostgreSQL run emitted one Alembic configuration deprecation warning; `path_separator=os` was added afterward. These are recorded troubleshooting events, not hidden successes.

## Exact successful execution commands

From the repository directory in PowerShell, after dependency installation/bootstrap:

```powershell
./scripts/portable-postgres.ps1
./scripts/run-tests.ps1
```

The test script supplies the generated database credential without printing it, selects `authflow_test`, runs `pytest -q -m 'not browser' --tb=short --junitxml=test-results/local.xml` and propagates its exit code. It resets only the named test database's application tables.

Chromium was installed locally, and TLS was regenerated after fixing the AKI defect:

```powershell
$env:PLAYWRIGHT_BROWSERS_PATH = (Join-Path (Get-Location).Path '.local/browsers')
.venv/Scripts/python.exe -m playwright install chromium
.venv/Scripts/python.exe scripts/bootstrap.py --renew-tls
./scripts/test-native-with-trust.ps1
```

The trust helper temporarily imports this project's CA into the current user's root store, starts the native HTTPS harness, runs `pytest tests/test_live.py -q --tb=short --junitxml=test-results/native-https.xml`, shuts down its HTTPS listeners and removes only the temporary CA. Existing trust is preserved if the CA was already installed. Hostname resolution is mapped only for the three fixed lab names; certificate chain and hostname verification are enabled. The hosts file was not changed.

In this execution, final verification detected that the original cleanup API had retained the CA. A subsequent `certutil -user -f -delstore Root <exact-generated-thumbprint>` succeeded, and the store was reopened to verify **zero matching entries**. The helper now uses that verified command and checks removal. Portable PostgreSQL was stopped after testing; its data remains available for the next launch.

```powershell
.venv/Scripts/python.exe -m ruff check .
.venv/Scripts/python.exe -m ruff format --check .
.venv/Scripts/python.exe -m compileall -q authflow scripts migrations tests
.venv/Scripts/python.exe -m pip check
.venv/Scripts/python.exe -m pip_audit -r requirements.lock --progress-spinner off
docker compose config --quiet
.venv/Scripts/python.exe scripts/report.py test-results/local.xml test-results/native-https.xml --output docs/observed-tests.md
```

See [the sanitized per-case report](observed-tests.md). Raw JUnit and runtime files are ignored; the report exporter includes only test names and statuses.

## Environment fingerprint and limitations

- Flask 3.1.3; SQLAlchemy 2.1.4; Alembic 1.20.0; psycopg 3.3.6; PyJWT 2.15.1; cryptography 50.0.2; Authlib 1.9.1; joserfc 1.7.5; Playwright 1.64.0. All transitive versions are in requirements.lock.
- Chromium 156.0.8078.4, Playwright build 1248.
- Official EDB portable archive: `postgresql-17.11-5-windows-x64-binaries.zip`; observed SHA-256 `80379b2c04d51c30225532e0ae04509899141e9957ed096fe749d7fd9df8f82f`. This is a recorded download checksum, not a separately verified publisher signature.
- Docker Desktop startup failed with an inaccessible stale `dockerInference` socket. No factory reset or Docker data deletion was performed. Compose configuration validity does not establish container-runtime success.
- Native HTTPS uses Werkzeug in the test harness; Compose specifies Waitress and Caddy. Their deployment path still needs the documented Compose run on a working Linux Docker engine.

## Reproduce the container checks when Docker is available

Stop portable PostgreSQL first to free port 55432, then:

```powershell
./scripts/portable-postgres.ps1 -Stop
docker compose up -d --build
docker compose --profile test run --build --rm tests
.venv/Scripts/python.exe scripts/report.py test-results/results.xml
```

Container browser trust is installed inside the test container's NSS store; no Windows root-store or hosts changes are needed for that command. Tests marked skipped are never treated as passing evidence.
