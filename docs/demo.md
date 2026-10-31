# Four-minute demonstration

Prepare: run the full suite, open the sanitized report, start Compose, configure host aliases and browser trust, and obtain the synthetic password privately. Do not record credentials, token requests, browser history, HAR files or full callback URLs.

**0:00–0:40 — Goal and boundaries.** “I implemented an educational authorization server, a confidential server-side client and a resource API. This project demonstrates protocol validation and security testing, not a production identity provider.” Show the architecture and supported subset.

**0:40–1:40 — Successful flow.** Open the client. Start sign-in, enter the synthetic account off-camera, approve openid and notes:read, then read protected notes. Explain that authentication happens at the authorization server; the API makes an authorization decision using an access token. The browser only has opaque session cookies.

**1:40–2:30 — Three bindings.** Show the sequence diagram: state binds the browser callback, nonce binds the ID token, and the PKCE verifier binds code redemption. Client credentials identify the confidential application. Point out exact redirect matching and why destination validation precedes error redirects.

**2:30–3:30 — Attack regression.** Run `docker compose --profile test run --rm tests python -m pytest tests/test_protocol.py::test_atomic_concurrent_redemption_postgresql tests/test_protocol.py::test_missing_scope_and_id_token_substitution -q`. Explain that eight transactions contend for one code, exactly one may succeed, and subsequent valid replay revokes that access grant. An ID token cannot be used as an API bearer token.

When demonstrating with the tested Windows fallback, use `./scripts/run-tests.ps1` for this segment instead. It runs the complete 66-case non-browser suite against portable PostgreSQL, including both highlighted regressions. Keep the native HTTPS server running in a separate terminal during the browser segment.

**3:30–4:00 — Evidence and limits.** Show the requirements matrix and observed results. Mention the independent Authlib client, the HTTPS browser tests, and any checks that remain blocked. Close with future work: separate DB roles, structured redacted audit events, cleanup and key rotation. Do not imply these are already implemented.

Interview prompts: Why store only code hashes? Why does an in-memory consumed flag fail with multiple workers? Why is JWT optional in OAuth? Why are state and nonce different? Why cannot a valid signature alone establish that a token is appropriate for the API?

