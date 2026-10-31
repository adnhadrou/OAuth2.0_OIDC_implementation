# Implementation log

## Frontend simplification

Kept the small browser demonstration because simplifying its six templates was less work than replacing the interactive OAuth flow with a console client. Reduced the large branding, used compact neutral forms, made secondary actions visually distinct, added short permission explanations and responsive spacing, and explicitly excluded hidden CSRF fields from input styling. No protocol handlers changed. Rendered all six screen states at 1280px and 375px in Chromium; checked one page heading, no horizontal overflow and hidden form fields. Inspected desktop login and mobile consent screenshots. Rebuilt the running Docker services so the change is immediately available. The Windows live-browser retest was blocked by certificate-store import error 0x80092004; this is separate from the successful static browser rendering checks.

## 2026-10-16 — Environment and design

Frontend follow-up validation: the refreshed Docker deployment passed the two selected live tests (trusted/untrusted TLS and independent Authlib login/consent/token/API exchange). The two Chromium live-flow tests were deselected in that container command; they were not represented as passing on the new pages.

Inspected the project root: only an existing main.py, IDE metadata and an unrelated virtual environment. Created a separate authflow-lab directory and new virtual environment. Preserved all existing files. Python 3.14.3, Git and Docker Desktop were available; PostgreSQL was not installed and Docker's engine was initially stopped.

Selected three Flask applications, SQLAlchemy/Alembic/PostgreSQL, Argon2id, PyJWT/cryptography, Requests, Waitress, pytest/Hypothesis, Authlib/joserfc and Playwright. Resolved and pinned the full Python environment in requirements.lock. Checked RFC 6749/6750/7636/9700 and OpenID Core/Discovery primary sources. The subset excludes refresh tokens, public clients and advanced OIDC features.

## Vertical slice and security controls

Implemented authorization request validation, login, consent, hashed code persistence, row-locked code redemption, signed access tokens and API scope checks. Added replay-triggered access-grant revocation. Added separate ID tokens, discovery/JWKS, distinct validation profiles and browser state/nonce/PKCE bindings. Kept tokens server-side and rotated opaque browser session IDs on login. Implemented persistent attempt counters and form CSRF protection.

Used explicit commits before response delivery and rollback on 5xx failures. Added a signing-outage regression to verify consumption does not survive a failed token mint. Tightened Unicode comparisons so invalid state/CSRF values produce rejection instead of TypeError. Restricted service file mounts and excluded .env as well as .local from Docker builds.

## Validation and environment troubleshooting

The initial 23 pure token/PKCE tests passed. Adding the isolated unsafe-race fixture brought that group to 24. The advisory audit reported no known vulnerabilities in the resolved lock. These results alone do not verify PostgreSQL or browser behavior.

Docker startup failed before project containers ran: its inference manager could not access a stale local socket. A normal restart timed out; an attempt to move that socket to a backup also failed. No factory reset, volume deletion or settings rewrite was performed. Docker service startup checks remained separate from application failures.

Prepared an official EDB PostgreSQL 17 portable fallback in ignored .local, bound only to loopback, without installing a Windows service. Added a native HTTPS test runner using the same applications and certificates, with exact lab-name DNS mapping and full TLS verification. Added a server mode for local demonstration when Docker is unavailable. Actual final executions and remaining blockers are recorded in test-results.md, rather than inferred from the code.

PostgreSQL 17.11 started successfully. The first host integration run was denied a loopback connection by the execution sandbox; the approved external run passed all 66 selected tests, including the eight-request race. The first live HTTPS run exposed a real certificate-generation defect: Python 3.14's strict verification required Authority Key Identifier. Added AKI/SKI and explicit key usage, regenerated only TLS material and retained strict certificate verification. Added an untrusted-CA rejection test. A noninteractive PowerShell certificate-provider removal failed; the Windows certificate-store API removed the exact temporary root successfully and is now used in the cleanup helper.

## Deferred work

Final application validation: 66 non-browser tests passed against PostgreSQL 17.11, followed by four real HTTPS/browser/interoperability tests. Generated sanitized per-case results and updated every matrix row from observed evidence. Compose configuration parsing, lint, formatting, compilation and dependency checks passed. The container-runtime path and GitHub-hosted CI remain unexecuted due to the local Docker failure and the instruction not to publish.

Final cleanup verification found that the certificate-store API had retained the temporary CA despite returning without an error. `certutil -user -f -delstore Root` removed the exact entry successfully; reopening the user store confirmed zero matching certificates. Updated the cleanup helper to use this verified method and fail if trust remains. Stopped the project-local PostgreSQL instance after tests. No test HTTPS listeners remain running.

Optional refresh-token rotation, signing-key rotation, Keycloak comparison and global logout were not added. Production hardening—separate database roles, retention jobs, structured redacted audit events and stronger abuse controls—remains explicitly outside the delivered subset.

## GitHub readiness follow-up — 2026-10-31

Resolved new dependency advisories by updating certifi to 2026.10.18, filelock to 4.2.1 and joserfc to 1.7.6 through a clean environment and verified lock. The updated audit found no known vulnerabilities. Rebuilt the application and browser-test images and executed the complete suite through Caddy and PostgreSQL: **70 passed, no failures or skips**. This closes the earlier Docker and refreshed-frontend browser-validation gaps. All three verified HTTPS health endpoints returned 200 afterward.

Added explicit LF rules for shell scripts/workflows, strengthened secret-file exclusions, repaired requirements-matrix encoding and updated the README links. Bootstrap repeatability, publication candidates and documentation links were checked. No application logic changed, no host trust settings changed, and no GitHub push occurred. See [the final check](final-check-2026-10-31.md) for commands and remaining initial-commit/remote setup.
