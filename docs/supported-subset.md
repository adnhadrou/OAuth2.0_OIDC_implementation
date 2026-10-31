# Supported features and deliberate limits

| Area | Implemented contract |
|---|---|
| Registration | Two static confidential clients: demo-web and second-web; second-web is a binding/interoperability test identity, not a second interactive application |
| OAuth grant | Authorization Code only; query authorization response; POST form token endpoint |
| Authentication | client_secret_basic only; reject body credentials and multiple authentication mechanisms |
| PKCE | S256 mandatory for both clients; 43–128 character verifier syntax; no plain fallback |
| User authentication | Synthetic student account, Argon2id password hash, database-backed account/IP login attempt limits |
| Consent | Explicit allow/deny, no remembered grants or partial scope selection |
| Codes | 256-bit random; SHA-256 at rest; 60-second lifetime; client, redirect, user, scope, nonce and challenge bindings |
| Consumption | PostgreSQL SELECT FOR UPDATE; one successful redemption; correctly bound replay revokes the access grant |
| Access token | RS256 JWT; five-minute lifetime; only Authorization: Bearer accepted by the API |
| OIDC | openid scope, signed ID token, nonce, discovery, JWKS, public subject identifier |
| Client | state, nonce, PKCE, server-side tokens, secure session cookies, CSRF-protected forms |
| TLS | Local private CA; consistent public issuer across browser/containers; verified backchannel requests |

## Standards requirements versus lab policies

The references are implemented as a limited educational subset. The table describes specific decisions and does not assert compliance with every MUST in every referenced standard.

| Decision | Basis |
|---|---|
| Authenticate confidential clients; bind the code to client and redirect | RFC 6749 §§3.2.1, 4.1.3 |
| Reject replay; short lifetime; revoke derived access grant after a correctly bound replay | RFC 6749 §4.1.2 (revocation is SHOULD) |
| Validate verifier against S256 challenge | RFC 7636 §§4.2–4.6 |
| Require S256 even for confidential clients; never permit plain | Stricter lab policy informed by RFC 9700 §2.1.1 and §4.8 |
| Exact registered redirect match; never redirect to an unvalidated destination | RFC 9700 §4.1.3 and RFC 6749 §4.1.2.1 |
| Require nonce length 16–256 whenever openid is requested | Lab policy; nonce is optional in the OIDC code flow, but MUST be checked when sent |
| Require state for this web client's own transaction | Lab policy with explicit browser CSRF binding; state is not universally required by OAuth |
| Separate token validation rules; algorithm allowlist | JWT security BCP RFC 8725 §§3.1, 3.8, 3.12; OIDC Core §3.1.3.7 |
| Bearer error challenges, no query-string token transport | RFC 6750 §3; RFC 9700 §4.3 |
| 60-second codes, 300-second tokens, 30-minute sessions | Concrete lab lifetime policies, not mandatory protocol constants |

## Token profiles

JWT access tokens are a **local implementation choice**, not an OAuth requirement. Opaque access tokens would also work with server-side lookup. This lab does not claim full RFC 9068 conformance.

Access header: `alg=RS256`, `typ=at+jwt`, configured `kid`. Required claims: `iss` (exact configured issuer), `aud` (exact API origin), `sub`, `iat`, `exp`, `jti` (code hash used as grant ID), `client_id`, string `scope`, and `token_use=access`. API validation checks signature, algorithm, type, issuer, audience, times, grant revocation and required scope. Its database lookup makes revocation immediate for subsequent API requests, at the cost of a database dependency. Previously completed requests cannot be undone.

ID header: `alg=RS256`, `typ=JWT`, configured `kid`. Claims: `iss`, `sub`, client-specific `aud`, `iat`, `exp`, transaction `nonce`, and `auth_time`. The demonstration client accepts only its own audience and matching nonce. An ID token is rejected by the API because its type, audience and claims differ. `at_hash` is omitted in this code-flow subset; tokens are returned together over a verified TLS token response.

Only fixed issuer `/jwks` keys are trusted. JWT-supplied `jku`, `x5u`, embedded `jwk` and critical extensions are rejected. `none`, HMAC algorithms and unexpected RSA algorithms are rejected before signature verification. Key material is cached for five minutes; key rotation is outside scope. No dynamic discovery or token-selected URL is accepted by the main client or API.

## Unsupported / operational limits

No UserInfo endpoint, profile/email claims, implicit/hybrid/password/client-credentials grants, public/native clients, refresh tokens, dynamic registration, request objects, PAR/JAR, advanced prompt/max_age/claims processing, federation, MFA, SAML, logout protocol, key rotation or global session revocation. Recognized unsupported authorization extensions are rejected; unknown parameters are ignored according to the OAuth extension model.

One issuer and one active signing key. No conformance suite certification. No production DoS guarantees: the attempt limiter is deliberately simple, account lockouts can be induced, and the IP bucket conservatively sees Caddy's internal address. There is no token-endpoint distributed abuse limiter. Browser state and expired code records need operational retention/cleanup work. Shared database role and trusted internal HTTP are local-demo constraints. A client session reset does not invalidate the authorization-server session. ID tokens already delivered cannot be recalled on code replay; they expire and cannot authorize API access.

## Primary references

- [RFC 6749](https://www.rfc-editor.org/rfc/rfc6749.html), Authorization Code and errors
- [RFC 6750](https://www.rfc-editor.org/rfc/rfc6750.html), bearer token use
- [RFC 7636](https://www.rfc-editor.org/rfc/rfc7636.html), PKCE
- [RFC 9700](https://www.rfc-editor.org/rfc/rfc9700.html), updated OAuth security guidance
- [OIDC Core](https://openid.net/specs/openid-connect-core-1_0.html), code flow and ID-token validation
- [OIDC Discovery](https://openid.net/specs/openid-connect-discovery-1_0.html), provider metadata
- [RFC 8725](https://www.rfc-editor.org/rfc/rfc8725.html), JWT validation best practices

