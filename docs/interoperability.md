# Independent-client interoperability

`tests/test_live.py::test_independent_authlib_oidc_client` uses Authlib 1.9.1's Requests OAuth2Session against the server's actual HTTPS endpoints. Authlib generates the authorization URL and S256 challenge, validates callback state during token exchange and performs client_secret_basic authentication. A separate requests cookie jar performs the synthetic user's login and consent. This is independent client code, not the handwritten demonstration client.

The test retrieves discovery metadata, requires the configured issuer, follows only that provider's advertised endpoints, retrieves JWKS over verified HTTPS, verifies RS256 with joserfc 1.7.5 and validates OIDC claims with Authlib's CodeIDToken. The nonce and audience must match the initiating client. Finally it calls the protected API with the returned access token.

Configuration: issuer `https://auth.authflow.test:8443`; client `demo-web`; redirect `https://client.authflow.test:8444/callback`; scopes `openid notes:read`; response type code; S256; client_secret_basic. Secret comes from the local bootstrap file and is never committed. TLS CA is `.local/ca.pem`. The default handwritten client pins its endpoints instead of implementing dynamic discovery; this test exercises the discovery contract independently.

Reproduce: `docker compose --profile test run --rm tests python -m pytest tests/test_live.py::test_independent_authlib_oidc_client -q`. See [test results](test-results.md) for the observed outcome and any host fallback used. This is a compatibility check for one configuration, not OpenID certification or proof of broad interoperability. Keycloak comparison was optional and is not implemented. No external provider vulnerability is asserted.

