# GitHub readiness check — 2026-10-31

**Result: ready to publish as the documented educational OAuth/OIDC lab.** The full Docker deployment and test suite passed after three dependency security updates. This is not a production-readiness or OIDC certification claim.

## Executed checks

| Check | Result |
|---|---|
| Full suite in the Linux Docker test image | **70 passed**, 0 failures, 0 errors, 0 skipped; 11.787 seconds in JUnit |
| Chromium login, consent, callback and API flow | PASS in the full suite |
| Browser callback-state attack rejection | PASS in the full suite |
| Eight concurrent code redemptions | PASS: one success and seven invalid-grant responses |
| Independent Authlib client and ID-token validation | PASS in the full suite |
| Trusted and untrusted HTTPS CA checks | PASS in the full suite; no TLS verification bypass |
| Docker build, migrations and service startup | PASS |
| Three HTTPS health endpoints after testing | All returned 200 using the lab CA |
| Ruff lint and formatting | PASS; 37 Python files already formatted |
| Python compilation | PASS |
| Dependency consistency | PASS in clean Windows environment, normal project environment and application container |
| Fresh bootstrap and repeat-run preservation | PASS in an isolated ignored directory; leaf certificate signature and all three DNS names checked |
| Fresh pip-audit of updated requirements.lock | No known vulnerabilities found at check time |
| Git publication review | Generated credentials, private keys, virtual environments and raw results excluded; no local credential values or checked credential/key patterns found in eligible files |
| Documentation | Local links checked; requirements-matrix encoding repaired |

The [sanitized per-case report](final-2026-10-31-tests.md) is safe to commit. Raw JUnit remains in ignored `test-results/final-2026-10-31.xml`. The publication scan covered the actual local generated credentials, private-key blocks, common GitHub-token/AWS-access-key patterns and oversized files. It is a bounded check, not proof that every possible secret format has been detected.

## Fixes made

The initial advisory audit identified affected versions of three dependencies. Updated `certifi` from 2026.7.22 to **2026.10.18**, `filelock` from 4.2.0 to **4.2.1**, and `joserfc` from 1.7.5 to **1.7.6**. Installed the candidate lock into a clean Python environment, verified the resolved package set, regenerated the lock, audited it, synchronized the normal project environment and rebuilt the containers. Other package versions were preserved.

Added `.gitattributes` for LF shell-script and workflow line endings. Expanded Git and Docker exclusions for environment backups, IDE files and key material. Repaired garbled UTF-8 symbols in the requirements matrix and linked the study guide and infographic from the README. Application protocol logic was unchanged.

## Reproduction

Run from the repository root, `authflow-lab`, after the README bootstrap steps:

```powershell
.venv/Scripts/python.exe -m ruff check .
.venv/Scripts/python.exe -m ruff format --check .
.venv/Scripts/python.exe -m pip check
.venv/Scripts/python.exe -m pip_audit -r requirements.lock --progress-spinner off
docker compose build auth client api migrate tests
docker compose up -d
docker compose --profile test run --rm tests python -m pytest -q --tb=no --junitxml=test-results/final-2026-10-31.xml
.venv/Scripts/python.exe scripts/report.py test-results/final-2026-10-31.xml --output docs/final-2026-10-31-tests.md
```

The browser test container imports the lab CA into its own NSS trust store. This run required no Windows certificate-store or hosts-file changes. PostgreSQL tests reset only `authflow_test`; the application database and Docker volume were preserved. Services were left running for local use.

## Environment and remaining publication steps

Host Python: 3.14.3. Application container Python: 3.14.10. PostgreSQL: 17.11. Docker Engine: 29.2.1. Playwright: 1.64.0 with Chromium 156.0.8078.4. Application base image used `python:3.14-slim@sha256:cd89c30eda26ee911a4611b18680086e0ea42e6f5f8cbe653d07fa7958c9cec8`.

Updated lock SHA-256: `a176956312a29b001626b1acea562b7bfd573d542d8437090b1a92bb7f23baa8`.

The Git repository is the **authflow-lab subdirectory**, not its parent PyCharm workspace. At check time it was on `main`, with no commits and no remote configured. No commit, GitHub repository creation or push was performed. Create the initial commit and configure the intended GitHub remote before pushing. The supplied GitHub Actions workflow has not yet run on GitHub; its first hosted result will only be available after publication.

The [documented scope and limitations](supported-subset.md) remain in effect, including no refresh tokens, signing-key rotation, MFA or OIDC logout, and a shared database role on a trusted local network.
