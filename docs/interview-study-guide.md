# AuthFlow Lab: concepts and interview study guide

Prepared 2026-10-19 from the implementation and its recorded test results. This is a study guide, not a claim that the project is a complete identity provider. The code references are relative to this document. Standards links distinguish general concepts from local implementation decisions.

## 1. Explain the project in one minute

> AuthFlow Lab is an educational implementation of a documented OAuth 2.0 and OpenID Connect subset. It has three Flask services: an authorization server, a confidential web client, and a protected API. The client uses Authorization Code with S256 PKCE. OIDC supplies an ID token for client login, while an access token authorizes API requests. Tokens stay on the server; the browser holds an opaque session cookie. I focused on strict token validation, binding each code to its client and transaction, and preventing concurrent code redemption with PostgreSQL row locking. Tests include negative security cases, an eight-request redemption race, browser flows and an independent Authlib client. It is a learning project with explicit operational limitations.

Adapt this wording to work you can explain and demonstrate. If asked about assistance, describe it honestly; understanding and verifying generated code is different from writing every line unaided.

The central lesson: identity security depends on checking who issued a credential, who it is intended for, which transaction created it, what it permits, and whether it is still usable.

## 2. The vocabulary

| Concept | Meaning in this project |
|---|---|
| Authentication | Establishing identity. The authorization server verifies a password; the client subsequently verifies an ID token. |
| Authorization | Deciding whether an operation is allowed. The API requires a valid access token and `notes:read`. |
| Resource owner | The synthetic student whose authorization is requested. |
| User agent | The browser that follows redirects and submits forms. |
| OAuth client | The server-side Flask application `demo-web`, not the human and not merely the browser. |
| Authorization server / OpenID Provider | The service that authenticates the user, collects consent, issues codes and signs tokens. |
| Resource server | The API exposing `/notes`. |
| Relying Party | OIDC's name for the client relying on the provider's identity assertion. |
| Grant | The authorization basis for issuing an access token. Here the flow uses an authorization code. |
| Scope | A named permission or requested capability. `notes:read` permits the demonstrated read operation. |
| Claim | A statement inside a token, such as its issuer, subject or expiry. |
| Issuer | The authority identified by the token's `iss`. |
| Audience | The intended recipient identified by `aud`. |
| Consent | The user's approval of the requested access; separate from password authentication. |
| Trust boundary | A point where data crosses between components with different authority. Validation belongs at these boundaries. |

OAuth provides an authorization framework, including delegated access. OIDC adds an identity layer using an ID token and defined validation rules. OAuth alone does not define a general-purpose login assertion for the client. See [OAuth 2.0](https://www.rfc-editor.org/rfc/rfc6749.html#section-1) and [OIDC introduction](https://openid.net/specs/openid-connect-core-1_0.html#Introduction).

Example: recognizing the student is authentication; permitting that student's client to read notes is authorization. A successfully authenticated user does not automatically have every permission.

## 3. Understand the architecture and its boundaries

The browser talks to the web client and authorization server. The web client exchanges a code directly with the authorization server, then calls the API directly. The browser receives rendered pages, not the issued tokens.

| Component | Job | Code |
|---|---|---|
| Authorization server | Request validation, login, consent, code issuance, code redemption, metadata and public keys | [authorization.py](../authflow/authorization.py) |
| Web client | Start login, maintain state/nonce/verifier, process callback, validate ID token, call API | [client.py](../authflow/client.py) |
| Resource API | Validate access token, check grant status and scope | [resource.py](../authflow/resource.py) |
| Security helpers | Secure randomness, hashing, PKCE, token issuance and token validation | [security.py](../authflow/security.py) |
| Common request layer | Server-side sessions, database transactions, cookies, CSRF and response headers | [common.py](../authflow/common.py) |
| Persistence | Users, codes, browser sessions and login throttle records | [models.py](../authflow/models.py) |
| Configuration | Issuer, origins, clients, keys and lifetimes | [config.py](../authflow/config.py) |

Caddy terminates public HTTPS. Backend HTTP and PostgreSQL operate on a trusted local Docker network. The services share a database role, which means logical service separation is stronger than database isolation in this lab.

The configured public issuer is `https://auth.authflow.test:8443`. It stays the same in browser redirects, metadata and JWT claims even when Docker resolves that hostname internally. An internal container address must not accidentally become a different issuer.

## 4. Walk through the complete login and API flow

1. The browser submits the client's `/start` form with a form-CSRF value.
2. The client generates independent random `state`, `nonce` and PKCE `code_verifier` values. It stores them in the server-side browser session with a five-minute deadline.
3. The client calculates the S256 challenge and redirects the browser to `/authorize` with `response_type=code`, its client ID, exact registered callback, `scope=openid notes:read`, state, nonce and challenge.
4. The authorization server checks the client, redirect, scopes, response type and PKCE requirements. An invalid destination is rejected locally, without redirecting to it.
5. The user authenticates at the authorization server. Password verification and consent are separate steps. An existing authorization-server session can avoid another password prompt.
6. On approval, the server generates a random code. It stores only its hash, bound to the client, callback, user, scopes, challenge and nonce. The code expires after 60 seconds.
7. The authorization server redirects the browser to the registered client callback with `code` and `state`.
8. The client checks the callback against the initiating browser's stored transaction and consumes that transaction, including on failure.
9. The client sends a server-to-server POST to `/token`. It supplies the code, original callback and verifier, and authenticates using HTTP Basic with its client ID and secret. TLS protects this exchange.
10. The authorization server locks the matching code record, validates all bindings, rejects expiry/reuse and marks a valid unused code consumed. Database commit occurs before the response is delivered.
11. The token response contains an access token and, because `openid` was requested, an ID token. The client validates the ID token and rotates its browser session identifier.
12. The browser asks the client to fetch notes. The client sends the access token in an Authorization header to the API. The API checks token validity, grant status and `notes:read`, then returns synthetic notes.

Browser-carried redirects are the **front channel**. Direct server requests such as the token exchange are the **back channel**. Both need appropriate protection. The authorization code passes through the browser; the issued tokens do not in this implementation.

## 5. Distinguish every credential and transaction value

| Value | Purpose | Handling here |
|---|---|---|
| User password | Authenticate the student to the authorization server | Submitted to that server; persisted as an Argon2id hash |
| Client ID | Identify the registered application | Public identifier; not proof of identity |
| Client secret | Authenticate the confidential client at `/token` | Kept on the backend; never placed in browser code |
| Authorization code | Short-lived intermediate credential exchanged for tokens | Browser callback; stored as SHA-256 digest; single use |
| PKCE verifier | Prove possession of the secret associated with the original challenge | Per transaction; stored by client; sent only in token exchange |
| State | Correlate callback with the initiating browser transaction | Sent outward, returned unchanged, checked against session |
| Nonce | Correlate ID token with the client's login transaction | Sent in request, copied into ID token, checked by client |
| Access token | Authorize access to the resource API | Server-side storage; sent to API |
| ID token | Provide an identity assertion to the client | Validated by client; not used as API authorization |
| Session cookie | Identify the browser's local application session | Opaque random value; session data lives in PostgreSQL |
| Form-CSRF value | Bind form submission to the application session | Hidden form field checked on POST |
| Refresh token | Obtain a new access token without repeating the full interactive flow | Not implemented |

The most common interview confusion is treating these as interchangeable. The client secret identifies an application; the verifier binds a particular code exchange; state binds the callback to a browser transaction; nonce binds an ID token to a login transaction.

## 6. PKCE: what it does and what it cannot do

PKCE means Proof Key for Code Exchange. The S256 calculation is:

```text
code_challenge = BASE64URL(SHA256(ASCII(code_verifier)))
```

Base64url padding is removed. A verifier has 43–128 allowed characters. The server stores the challenge, recomputes it from the supplied verifier during redemption and compares the result. See [RFC 7636](https://www.rfc-editor.org/rfc/rfc7636.html#section-4).

In this lab, an intercepted code alone is insufficient to obtain tokens: redemption also needs the right verifier and confidential-client authentication. The public challenge does not disclose a high-entropy verifier. S256 is hashing, not encryption.

The lab requires S256 even for confidential clients and rejects `plain` or missing challenges. A client secret alone does not establish which authorization transaction produced a code.

PKCE does not encrypt tokens, authenticate the user, replace HTTPS, or prevent reuse of an already stolen bearer access token. It also does not make a compromised backend trustworthy.

## 7. State, nonce and form CSRF

State is compared with a random value in the specific browser session. An arbitrary nonempty state is insufficient. Without transaction binding, an attacker may cause a browser to finish an unintended login flow, including login as the attacker's account.

Nonce is checked only after ID-token signature and claim validation. A legitimate signed token from an unrelated login must not be accepted just because the issuer is trusted.

Form-CSRF protection covers `/start`, login, consent, notes and session clearing. OAuth state protects a callback relationship; it is not a replacement for protecting application forms.

The code-flow OIDC nonce is optional in the base specification, but a sent nonce must be checked. This lab makes it mandatory for `openid` requests. Similarly, this web client requires state; do not claim state is a universal mandatory parameter in every OAuth deployment. See [OIDC authentication request](https://openid.net/specs/openid-connect-core-1_0.html#AuthRequest) and [OAuth security guidance](https://www.rfc-editor.org/rfc/rfc9700.html#section-4.7).

## 8. JWTs and token validation

The project's signed JWTs contain three base64url segments: header, payload and signature. Decoding the first two segments does not validate the token. Signing provides integrity and evidence of the signer's key possession; it does not hide the payload. No encrypted JWT profile is implemented.

RS256 uses an RSA private signing key and SHA-256. The authorization server signs; other services verify with the public key. Giving the API a public key does not give it the ability to issue new valid tokens.

| Claim/header | Meaning and local check |
|---|---|
| `alg` | Only RS256 is accepted; the token cannot choose a new algorithm policy |
| `kid` | Selects a unique matching key within trusted issuer keys |
| `typ` | `at+jwt` for access tokens, `JWT` for this ID-token profile |
| `iss` | Must equal the configured issuer |
| `aud` | API origin for an access token; `demo-web` for the demonstration client's ID token |
| `sub` | Subject identifier; the user represented by the token |
| `iat` / `exp` | Issuance and expiry timestamps validated by the JWT library |
| `scope` | Space-separated permissions checked by API |
| `jti` | Here, the authorization-code digest doubles as grant identifier for status lookup |
| `client_id` | Client associated with the access token |
| `token_use` | Local access-token claim required to equal `access` |
| `nonce` | ID-token transaction value checked against client session |
| `auth_time` | Emitted in ID tokens to record user authentication time; advanced freshness policies are not implemented |

The validator checks header policy, selects an issuer key, verifies signature, enforces required claims and validates issuer, audience and time. It then applies token-specific checks. The API separately checks scope and database grant status.

A valid signature alone is insufficient: the token may target another API, be expired, or be the wrong token kind. Distinct token profiles reduce substitution attacks. This follows the reasoning in [JWT security best practices](https://www.rfc-editor.org/rfc/rfc8725.html#section-3).

OAuth does not require access tokens to be JWTs. An opaque access token can instead reference server-side authorization data. The lab's `token_use`, audience shape and grant identifier are local choices; the project does not claim complete JWT access-token profile conformance.

## 9. Discovery, JWKS and trust

Discovery exposes endpoint locations and supported capabilities at `/.well-known/openid-configuration`. JWKS publishes public verification keys at `/jwks`.

The main client and API use a fixed configured issuer and its fixed JWKS URL. They do not discover an arbitrary provider from an untrusted token. JWT headers requesting `jku`, `x5u`, embedded `jwk` or critical extensions are rejected. The `kid` selects a key only inside the trusted set; it cannot establish trust by itself.

Keys are cached for five minutes. Key rotation is not implemented. A future rotation design would publish new public keys before signing with them, retain old verification keys while old tokens remain valid, and coordinate cache refresh. Emergency compromise needs a different, faster invalidation policy.

TLS trust and JWT trust have different jobs: TLS authenticates the network endpoint and protects transport; the JWT signature binds token contents to an issuer key. Both matter here.

## 10. Bearer tokens, scope and object-level authorization

A bearer credential can be used by its possessor without demonstrating a separate cryptographic key. The API accepts it through `Authorization: Bearer ...`, rejects query-string access-token transport, and returns a bearer challenge on authentication failures. Missing/invalid credentials normally produce 401; a valid token lacking `notes:read` produces 403. See [bearer token usage](https://www.rfc-editor.org/rfc/rfc6750.html#section-2.1).

PKCE protects code exchange, not subsequent bearer requests. A stolen access token could be usable until expiry or effective revocation. The project limits exposure using server-side storage, verified HTTPS, short lifetimes, restrictive response policies and no token display.

Audience answers which service may accept the token; scope answers which permission it carries. Neither automatically proves ownership of a particular database object. A real `/notes/{id}` would also need a subject/tenant/ownership policy. This demonstration returns fixed synthetic data and does not implement a complete multitenant authorization system.

RBAC assigns permissions through roles; ABAC uses attributes of the user, resource and context. OAuth scopes can feed either policy model but do not implement them by themselves. Neither model is implemented as a general policy engine here.

## 11. The concurrency case study: your strongest engineering example

An unsafe implementation does this:

```text
Read code: unused
Issue tokens
Mark code consumed
```

Two requests can read the same unused value before either writes. Sequential replay tests do not reproduce this. A lock in one Python process also cannot coordinate independent workers or instances.

The actual endpoint selects the code with PostgreSQL `SELECT ... FOR UPDATE` inside a transaction. It checks client, redirect and verifier, then checks consumption and expiry. A valid unused code is marked consumed and tokens are generated. Commit happens before HTTP delivery. Another transaction waits for the lock, then observes the committed consumed state.

The recorded test uses eight competing requests and requires one successful token response and seven `invalid_grant` responses. A separate intentionally unsafe test fixture demonstrates the original race; it is not a discovered third-party vulnerability.

The deeper detail: correctly bound reuse also marks the grant revoked. Therefore, in an eight-request race, the one issued access token can subsequently become unusable because another request detects reuse. One successful issuance does not mean the resulting token remains authorized after replay detection.

Bindings are checked before revocation, so an unrelated client or a request with the wrong verifier cannot revoke another grant merely by presenting its code.

Failure cases matter:

- Signing failure before commit rolls back code consumption.
- A crash or connection loss after commit but before delivery can consume a code without the client receiving tokens. The client must restart login.
- HTTP delivery and a database commit are not one atomic operation; the design provides at-most-once successful redemption, not guaranteed exactly-once delivery.
- Holding locks while signing increases lock duration. Client browser-session rows also remain locked during backchannel work, which serializes requests from the same session and deserves attention at larger scale.

Read [the case study](case-study.md), [race fixture](../tests/test_race_exercise.py), and [protocol regression tests](../tests/test_protocol.py).

## 12. Revocation, expiry and sessions

The API uses the access token's `jti` to read the code/grant record. It requires that record to exist, be consumed and not be revoked. This lets a detected code replay invalidate future API checks before the JWT expires.

The design is therefore not stateless. Its advantage is online grant-status enforcement; its costs are database latency, availability dependence and coupling. A request that already passed its check cannot be retroactively undone by a later revocation.

This database lookup is a local mechanism, not a standards-based introspection endpoint. Introspection is a protocol through which a protected resource asks an authorization server about token status. See [RFC 7662](https://www.rfc-editor.org/rfc/rfc7662.html#section-2).

There are three separate clocks: authorization codes last 60 seconds, tokens 300 seconds, and browser sessions 1800 seconds. A still-valid web session can contain an expired access token. The UI may recognize the user while an API operation fails until login is restarted. The client login transaction also has its own five-minute deadline.

`Clear client session` rotates/removes the client's local session data. It does not terminate the authorization-server session or globally revoke tokens. An already-issued ID token is not recalled by access-grant revocation. Its original expiry also does not automatically end an application session established from it.

## 13. Cookies, passwords and browser protections

Cookies use `Secure`, `HttpOnly`, `SameSite=Lax`, a `__Host-` name, path `/` and no Domain attribute. The browser stores an opaque random session identifier; its SHA-256 digest indexes server-side state.

Secure restricts cookie transport to HTTPS. HttpOnly prevents direct JavaScript cookie access, although XSS could still act through the user's browser. Lax permits the top-level GET callback navigation needed here. SameSite is based on site, not origin; the lab's related subdomains can be same-site. Host-only cookies and explicit CSRF checks still matter.

Session identifiers rotate after successful authentication to reduce session fixation. The authorization server and client have separate sessions.

Passwords use Argon2id through a library. A slow, memory-hard password hash is appropriate because human passwords are guessable. Random 256-bit codes and session IDs use fast SHA-256 digests because brute-forcing their high-entropy values is a different problem. Hashing codes does not make a fully compromised database safe: browser-session records contain tokens and transaction secrets.

The login limiter persists counters in PostgreSQL: five attempts per account and twenty per observed IP per 60-second window. These are attempt limits, not just failed-password counters. A dummy password hash is verified for unknown users, reducing obvious account-existence timing differences without proving perfect timing indistinguishability.

The limiter is deliberately simple: an attacker can induce account lockout, Caddy's internal address may collapse the IP bucket, and there is no distributed token-endpoint abuse protection. Do not trust arbitrary forwarded-IP headers as a quick fix; proxy trust needs explicit configuration.

Responses use no-store, no-referrer, a restrictive CSP and anti-framing controls. These reduce caching, leakage and browser attack opportunities; they do not replace protocol validation. The 303 redirects also switch the next request to GET instead of forwarding password form bodies to a different destination.

## 14. Tests: what the evidence establishes

| Test category | Question it answers |
|---|---|
| Token tests | Are tampered signatures, unsupported algorithms, wrong claims and token types rejected? |
| Protocol tests | Are codes bound to the right client, callback and verifier, and is consent handled correctly? |
| Client tests | Does state belong to this browser and does the nonce match this login? |
| Concurrent PostgreSQL test | Can competing requests redeem one code more than once? |
| Browser tests | Do actual redirects, forms, cookies and rendered pages work together? |
| TLS tests | Does an untrusted CA fail and the explicit lab trust succeed? |
| Independent Authlib client | Can another implementation complete this supported flow? |

The recorded 2026-10-16 results contain 66 nonbrowser passes plus four native HTTPS/live passes across two runs. A later frontend follow-up recorded two live integration passes; a Windows certificate-store issue blocked a full browser rerun of those updated pages. Docker services were rebuilt, but a complete container suite was not rerun in that follow-up. These are historical results, not a fresh run for this guide. See [test-results.md](test-results.md).

A passing interoperability test is useful evidence, not OIDC certification. Passing tests do not establish complete security, load capacity or a coverage percentage. Skipped database tests must not be presented as passes. A dependency audit reflects advisories known at execution time.

## 15. Common interview questions and concise answers

1. **Why use OAuth instead of giving the client the user's password?** It lets the client obtain bounded access while the user authenticates at the authorization server. This client receives tokens rather than the student's password.
2. **Why add OIDC?** The client needs a defined identity assertion. It validates the ID token and uses its subject to establish its own session.
3. **Can the API accept an ID token?** This API must reject it: it targets the client and follows a different validation profile. It is not the API's authorization credential.
4. **Is every OAuth token a JWT?** No. JWT is a format choice; this lab uses it for access tokens and signed OIDC ID tokens.
5. **Is a JWT secret because it is encoded?** No. This signed token's payload is readable. Encoding, signing and encryption solve different problems.
6. **Why check audience after checking the signature?** A trusted issuer can sign tokens for other recipients. Signature validity does not authorize this API to accept every such token.
7. **Is the client ID a secret?** No. It identifies the app. This confidential client additionally authenticates with a secret at the token endpoint.
8. **What is a confidential client?** A client deployed where its credentials can be protected, such as this server-side application. Browser-only code cannot keep a distributed shared secret confidential.
9. **Why retain PKCE for a confidential client?** Client authentication and per-transaction code binding solve different problems; the lab requires both.
10. **Why not store tokens in localStorage?** The backend can hold them and expose only an opaque browser session. This reduces token exposure to browser scripts, while leaving browser CSRF/XSS protections necessary.
11. **What happens without `openid`?** The authorization server can issue an OAuth access token without an ID token. The demo login client itself requests `openid` because it needs identity.
12. **What is the difference between scope and audience?** Scope describes permitted operations; audience identifies the intended token recipient.
13. **How do you stop code reuse?** Enforce short lifetime, all code bindings and atomic single-use consumption; revoke the grant after correctly bound replay.
14. **Does a `consumed` boolean solve concurrency?** Only when the read/check/update is atomic. An unlocked check-then-write can succeed twice.
15. **Why PostgreSQL for tests instead of SQLite?** The guarantee under test depends on actual PostgreSQL transaction and row-lock behavior.
16. **Why strict redirect matching?** Sending a code to an attacker-controlled callback defeats the intended destination binding. Even error redirects must use an already-validated destination.
17. **Why reject duplicate parameters?** Different parsers can interpret them differently. Rejecting ambiguous duplicates removes that interpretation gap in the supported protocol requests.
18. **Why not follow a JWT's key URL?** The token is untrusted input. Allowing it to select its own trust source can enable forged-token acceptance or unwanted network requests.
19. **What happens if JWKS retrieval fails?** Cached keys can be used within the cache policy. If retrieval is needed and fails, validation does not silently succeed; the API can return 503 for network retrieval failure.
20. **What if the database is unavailable?** This API cannot establish current grant status. The current implementation does not provide a polished database-outage response path; availability handling needs improvement without bypassing authorization.
21. **Are refresh tokens supported?** No. Access-token expiry requires another authorization flow. A future design would need explicit storage, revocation and replay controls.
22. **Is this SSO?** The authorization server has a reusable login session, a building block for SSO. The lab does not demonstrate a complete enterprise SSO deployment or multiple interactive relying parties.
23. **What does the second client demonstrate?** `second-web` is a static registration for binding/interoperability tests, not a second full interactive application.
24. **Does logout immediately invalidate everything?** No. Local session removal, provider-session termination and token revocation are different operations; only local client session clearing is exposed here.
25. **Does PKCE prevent stolen access-token replay?** No. The issued access tokens remain bearer credentials.
26. **How would you reduce bearer replay risk further?** Evaluate sender-constrained tokens such as DPoP, which associate token use with a key and request proofs. This is a separate extension, not implemented here. See [RFC 9449](https://www.rfc-editor.org/rfc/rfc9449.html#section-2).
27. **Would you build your own identity provider in production?** This project makes the protocol visible for learning. A production decision would weigh established implementations, interoperability, operations and assurance rather than assuming this lab is ready.
28. **What was the hardest bug?** Explain the controlled code-redemption race, why sequential tests miss it, how row locking fixes issuance, and what replay revocation does afterward. Do not describe the exercise as a real-world CVE discovery.
29. **What does testing with Authlib prove?** It reduces the risk that the server only works with its own client. It tests the supported path, not every standard requirement.
30. **What is your biggest architectural tradeoff?** Database-backed revocation allows prompt status enforcement but couples every protected request to a shared database. The shared role and long-lived request transactions also limit isolation and scaling.

## 16. Adjacent concepts to recognize, without claiming implementation

The client-credentials grant is for a client acting on its own behalf, rather than this user's interactive login. A refresh token obtains replacement access tokens. Both are distinct from the supported authorization-code grant. See [OAuth grant and refresh definitions](https://www.rfc-editor.org/rfc/rfc6749.html#section-4.4).

Implicit flow exposes tokens in authorization responses and is not the flow used here. The password grant has the client collect the user's password; current OAuth security guidance prohibits that grant and discourages implicit access-token issuance. See [RFC 9700](https://www.rfc-editor.org/rfc/rfc9700.html#section-2).

MFA strengthens user authentication; it does not replace client binding or API authorization. Federation establishes identity relationships across systems; this lab has one issuer and no external identity provider. CORS controls browser cross-origin response access; it is not an authentication or authorization mechanism. Here the backend calls the API, so permissive browser CORS is unnecessary.

A real key-rotation or refresh-token extension must be designed as a lifecycle, including expiry, caching, compromise, revocation and concurrent requests. Adding a new token field is not enough.

## 17. What you would improve before a production use case

Prioritize by concrete requirements and threats:

1. Assess an established provider/library and formal conformance testing before expanding a custom protocol server.
2. Separate service database privileges and define a dedicated grant-status boundary instead of broad shared access.
3. Add managed signing-key storage, rotation, secret rotation and an emergency compromise procedure.
4. Improve user-account security: MFA requirements, recovery, registration and abuse controls.
5. Reduce transaction duration, handle database/JWKS outages deliberately, add cleanup of expired records, and test load and lock contention.
6. Design safe audit events and monitoring without logging tokens, codes or credentials.
7. Add only required protocol features, such as refresh tokens or logout, with their own threat models and negative tests.
8. Validate deployment isolation, backup/recovery, trusted proxy handling and internal network assumptions.

Unsupported features include refresh tokens, UserInfo, key rotation, dynamic registration, public/native clients, additional grants, MFA, federation and OIDC logout. Read [supported-subset.md](supported-subset.md) before making portfolio claims.

## 18. Practice until you can explain, not just recite

Work through these in order:

1. Draw the browser, client, authorization server and API. Place every credential where it actually travels.
2. Explain access token versus ID token, then state versus nonce versus verifier versus client secret.
3. Trace `/start` to `/callback` to `/notes` in the code. At each step, identify what is untrusted and what must be checked.
4. Explain the race with two timelines, then add the database lock and describe crash/retry behavior.
5. Pick five negative tests. State the attack, expected rejection and the remaining limitation.
6. Rehearse the one-minute explanation, then answer follow-ups without relying on exact wording.

For an unfamiliar interview question, state your assumption, identify the asset and trust boundary, describe the failure mode, propose a control and a test, and acknowledge the tradeoff. That reasoning transfers beyond this implementation better than memorizing a list of answers.
