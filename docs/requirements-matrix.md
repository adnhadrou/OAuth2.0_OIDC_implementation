# Requirements-to-tests matrix

Results are recorded in [test-results.md](test-results.md) and the [2026-10-31 per-case report](final-2026-10-31-tests.md). All listed automated tests passed in the full Linux Docker suite on 2026-10-31, including the current browser interface and PostgreSQL concurrency tests. References distinguish lab policy in the supported-subset document.

| Security property | Reference | Implementation | Test | Observed result |
|---|---|---|---|---|
| Login → code → tokens → API | RFC 6749 §4.1 | authorization.py, resource.py | test_login_code_token_api | PASS |
| Atomic single-use code under concurrency | RFC 6749 §4.1.2 | authorization.py:token; common.py:finish | test_atomic_concurrent_redemption_postgresql | PASS |
| Reused code rejected; derived access revoked | RFC 6749 §4.1.2 | authorization.py, resource.py | test_replay_revokes_existing_access | PASS |
| Expired code rejected | RFC 6749 §4.1.2 | authorization.py:token | test_expired_code | PASS |
| Client and redirect binding | RFC 6749 §4.1.3 | authorization.py:token | test_wrong_client_and_token_redirect_binding | PASS |
| Confidential client authentication | RFC 6749 §3.2.1 | authorization.py:authenticate_client | test_invalid_client_authentication | PASS |
| Mandatory verifier; wrong verifier rejected | RFC 7636 §4.6 | security.py; authorization.py:token | test_wrong_or_missing_pkce | PASS |
| No S256 downgrade | RFC 9700 §4.8; lab policy | authorization.py:authorize | test_pkce_downgrade; test_missing_challenge_and_nonce | PASS |
| Exact redirect and no untrusted error redirect | RFC 9700 §4.1.3 | authorization.py:authorize | test_redirect_exact_match | PASS |
| Duplicate parameters rejected | RFC 6749 §§3.1, 3.2 | authorization.py | test_duplicate_parameters_and_unsupported_grant | PASS |
| Consent denial and CSRF | RFC 6749 §10.12; lab forms policy | authorization.py; common.py:csrf | test_consent_denial_and_csrf | PASS |
| Persistent login throttle, secure cookies | Lab session policy | authorization.py; common.py | test_login_throttle_and_secure_cookies | PASS |
| State matches initiating browser; one use | RFC 6749 §10.12; client policy | client.py:callback | test_state_mismatch_never_exchanges_code; test_state_bound_to_initiating_browser_and_one_use | PASS |
| Transaction expiry and form CSRF | Lab policy | client.py; common.py | test_expired_state_and_form_csrf | PASS |
| Nonce and server-side token storage | OIDC Core §3.1.3.7 | client.py; security.py | test_callback_validates_nonce_and_keeps_tokens_server_side | PASS |
| Correct issuer/audience/time claims | OIDC Core §3.1.3.7; RFC 8725 | security.py:TokenValidator | test_token_claim_rejections | PASS |
| Invalid signature and unexpected algorithms | RFC 8725 §3.1 | security.py:TokenValidator | test_invalid_signature; test_unexpected_algorithm | PASS |
| Token-supplied key URLs not trusted | RFC 8725 §3.10; lab allowlist | security.py:TokenValidator | test_untrusted_key_headers | PASS |
| API rejects forged/misdirected/expired tokens | RFC 6750; access profile | resource.py | test_api_rejects_token_mutations | PASS |
| Scope enforcement; reject ID token at API | RFC 6750 §3.1; RFC 8725 §3.12 | resource.py; security.py | test_missing_scope_and_id_token_substitution | PASS |
| Token profiles separated | RFC 8725 §3.12 | security.py | test_cross_token_type_rejected; test_minted_tokens_have_distinct_audiences | PASS |
| OAuth without openid emits no ID token | OIDC Core §3.1.2.1 | security.py:mint | test_oauth_without_openid | PASS |
| Bearer challenge and rejected query token | RFC 6750 §3; RFC 9700 §4.3 | resource.py | test_bearer_errors | PASS |
| Accurate discovery; public-only JWKS | OIDC Discovery §3 | authorization.py | test_discovery_and_public_jwks | PASS |
| Signing failure cannot commit consumption | Transaction integrity | authorization.py; common.py | test_signing_failure_rolls_back_consumption | PASS |
| PKCE vector and controlled mutations | RFC 7636 Appendix B | security.py:challenge | test_rfc7636_vector; test_pkce_mutation_changes_challenge | PASS |
| Isolated introduced race reproduces | Educational exercise, not a CVE | test fixture only | test_introduced_check_then_set_flaw | PASS (flaw demonstrated) |
| Real browser login, callback, API and HttpOnly | Browser transaction policy | All three services | test_browser_login_callback_api; test_browser_callback_state_attack | PASS |
| Independent OIDC client compatibility | Supported OIDC subset | discovery, JWKS, token endpoint | test_independent_authlib_oidc_client | PASS |
| HTTPS requires the correct trust anchor | TLS trust / lab CA policy | bootstrap.py; verified requests | test_https_requires_trusted_ca | PASS |

Logging controls, local CA trust procedures and shared-role residual risks also require configuration review; the test suite does not claim exhaustive dynamic proof that no possible log message can contain a secret.
