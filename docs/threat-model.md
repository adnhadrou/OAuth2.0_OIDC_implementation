# Threat model

## Assets and boundaries

Assets: user password/hash, client secrets, signing/TLS keys, authorization codes, browser sessions, PKCE verifiers, access/ID tokens, consent and synthetic protected notes. Principal boundaries: browser to gateway; gateway to service; client to issuer/API; services to database; issuer private key to public JWKS. Host administrator and Docker control are trusted. A hostile container or compromised database role is outside the isolation guarantees of this deployment.

Attacker capabilities: send arbitrary authorization and token requests, operate another registered synthetic client, change redirects and scopes, inject callback parameters, steal a code without its verifier, replay/race a code, present attacker-signed or misdirected tokens, and submit cross-site forms. The attacker cannot break TLS or RSA, read the client database, or steal all local keys under this model.

| Threat | Mitigation and test evidence | Residual limit |
|---|---|---|
| Redirect exfiltration | Validate destination before redirect; exact string tests | No dynamic registration |
| Code interception/injection | Mandatory S256, client/URI binding, browser state | Full client/session compromise defeats these controls |
| Concurrent code replay | PG row lock and commit-before-delivery; eight-worker test | Valid replay revokes the winning access grant; start a new flow |
| Login/callback CSRF | CSRF form token, browser-bound state, nonce, transaction expiry | One outstanding flow per session; XSS would weaken browser protections |
| Session fixation/theft | Random identifier, hash at rest, rotation, Secure/HttpOnly/__Host/Lax | Database session payload contains tokens |
| Token confusion | Separate typ/aud/claim profiles and explicit algorithm allowlist | One signing key shared by token types; validators must remain strict |
| Key URL injection | Fixed HTTPS JWKS URI, reject jku/x5u/jwk | Issuer and CA compromise remain fatal |
| Brute-force login | Argon2id, generic failures, persistent account/IP counters | Simple limiter can cause denial of service; no MFA |
| Scope escalation | Registered-scope allowlist, bound grant, API notes:read enforcement | Consent grants the complete displayed set |
| Secret logging | No request logs, no token rendering, sanitized reports | Debug/HAR tooling can still expose synthetic secrets if manually enabled |
| Database injection | SQLAlchemy bound parameters | Shared privileged DB role is not a production boundary |
| Malicious framing / referrer leak | CSP frame-ancestors none, no-referrer, no-store | Codes briefly exist in callback URLs; avoid browsing traces |

Local CA trust expands what the trusted user/browser accepts. The CA private key is discarded immediately after issuing the lab server certificate, and private leaf keys are ignored by Git. Remove the trust anchor when done. Use only a private machine/account; no Internet-facing hosting is part of this design.

Tests prove rejection for their supplied inputs and execution environment, not the absence of every vulnerability. The intentionally unsafe race demonstration is isolated in a test fixture; no insecure feature flag exists in the application.

