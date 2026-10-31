from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from urllib.parse import parse_qs, urlencode, urlsplit

import jwt
import pytest
from werkzeug.datastructures import MultiDict

from authflow.models import Code
from authflow.security import TokenValidator, digest, public_jwk
from tests.conftest import authorize_params, csrf_value, expire_code, issue, redeem

pytestmark = pytest.mark.integration


def api_get(lab, token):
    return lab["api"].test_client().get("/notes", headers={"Authorization": "Bearer " + token})


def test_login_code_token_api(lab):
    nonce = "n" * 32
    code = issue(lab, nonce=nonce)
    response = redeem(lab, code)
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    tokens = response.json
    validator = TokenValidator(lab["settings"], {"keys": [public_jwk(lab["settings"])]})
    claims = validator.validate(tokens["id_token"], "id", nonce)
    assert claims["sub"] == "student-001"
    assert api_get(lab, tokens["access_token"]).status_code == 200
    with lab["sessions"]() as db:
        stored = db.get(Code, digest(code))
        assert stored.consumed and stored.digest != code


def test_replay_revokes_existing_access(lab):
    code = issue(lab)
    token = redeem(lab, code).json["access_token"]
    assert api_get(lab, token).status_code == 200
    assert redeem(lab, code).json == {"error": "invalid_grant"}
    assert api_get(lab, token).status_code == 401


def test_expired_code(lab):
    code = issue(lab)
    expire_code(lab, code)
    assert redeem(lab, code).json == {"error": "invalid_grant"}


@pytest.mark.parametrize("verifier", [None, "", "x" * 43, "v" * 42, "v" * 129, "é" * 43])
def test_wrong_or_missing_pkce(lab, verifier):
    code = issue(lab)
    assert redeem(lab, code, code_verifier=verifier).json == {"error": "invalid_grant"}
    assert redeem(lab, code).status_code == 200  # A bad attempt cannot consume someone else's code.


@pytest.mark.parametrize("method", ["plain", "s256", "S512", ""])
def test_pkce_downgrade(lab, method):
    params = authorize_params(lab["settings"], code_challenge_method=method)
    result = lab["auth"].test_client().get("/authorize?" + urlencode(params))
    assert parse_qs(urlsplit(result.location).query)["error"] == ["invalid_request"]


def test_missing_challenge_and_nonce(lab):
    for field in ("code_challenge", "nonce", "code_challenge_method"):
        params = authorize_params(lab["settings"])
        del params[field]
        result = lab["auth"].test_client().get("/authorize?" + urlencode(params))
        assert parse_qs(urlsplit(result.location).query)["error"] == ["invalid_request"]


@pytest.mark.parametrize("suffix", ["/", "?evil=1", "#fragment", ".evil.test", "%2f"])
def test_redirect_exact_match(lab, suffix):
    params = authorize_params(lab["settings"])
    params["redirect_uri"] += suffix
    result = lab["auth"].test_client().get("/authorize?" + urlencode(params))
    assert result.status_code == 400
    assert "Location" not in result.headers


def test_wrong_client_and_token_redirect_binding(lab):
    code = issue(lab)
    assert redeem(lab, code, client="second-web").json == {"error": "invalid_grant"}
    assert redeem(lab, code, redirect_uri="https://evil.test/callback").json == {
        "error": "invalid_grant"
    }
    assert redeem(lab, code).status_code == 200


def test_invalid_client_authentication(lab):
    code = issue(lab)
    for auth in [None, ("demo-web", "wrong"), ("unknown", "wrong")]:
        response = (
            lab["auth"]
            .test_client()
            .post(
                "/token",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                },
                auth=auth,
            )
        )
        assert response.status_code == 401
        assert response.json == {"error": "invalid_client"}
        assert response.headers["WWW-Authenticate"].startswith("Basic")
    assert redeem(lab, code, client_secret="body-secret").status_code == 401


def test_atomic_concurrent_redemption_postgresql(lab):
    code = issue(lab)
    barrier = Barrier(8)

    def exchange(_):
        barrier.wait(timeout=10)
        response = redeem(lab, code)
        return response.status_code, response.json.get("error")

    with ThreadPoolExecutor(max_workers=8) as pool:
        statuses = list(pool.map(exchange, range(8)))
    assert statuses.count((200, None)) == 1
    assert statuses.count((400, "invalid_grant")) == 7
    with lab["sessions"]() as db:
        assert db.get(Code, digest(code)).consumed


def test_missing_scope_and_id_token_substitution(lab):
    tokens = redeem(lab, issue(lab, scope="openid")).json
    response = api_get(lab, tokens["access_token"])
    assert response.status_code == 403
    assert 'scope="notes:read"' in response.headers["WWW-Authenticate"]
    assert api_get(lab, tokens["id_token"]).status_code == 401


def test_oauth_without_openid(lab):
    tokens = redeem(lab, issue(lab, scope="notes:read")).json
    assert "id_token" not in tokens
    assert api_get(lab, tokens["access_token"]).status_code == 200


def test_duplicate_parameters_and_unsupported_grant(lab):
    params = MultiDict(authorize_params(lab["settings"]))
    params.add("redirect_uri", "https://evil.test")
    result = lab["auth"].test_client().get("/authorize", query_string=params)
    assert result.status_code == 400 and "Location" not in result.headers
    code = issue(lab)
    assert redeem(lab, code, grant_type="password").json == {"error": "unsupported_grant_type"}
    form = MultiDict({"grant_type": "authorization_code", "code": code})
    form.add("code", "other-code")
    assert lab["auth"].test_client().post("/token", data=form).json == {"error": "invalid_request"}


def test_consent_denial_and_csrf(lab):
    browser = lab["auth"].test_client()
    settings = lab["settings"]
    params = authorize_params(settings)
    browser.get("/authorize?" + urlencode(params), base_url=settings.issuer)
    login = browser.get("/login", base_url=settings.issuer)
    assert browser.post("/login", base_url=settings.issuer, data={}).status_code == 400
    assert (
        browser.post(
            "/login",
            base_url=settings.issuer,
            data={
                "csrf": csrf_value(login),
                "username": "student",
                "password": settings.login_password,
            },
        ).status_code
        == 303
    )
    consent = browser.get("/consent", base_url=settings.issuer)
    assert browser.post("/consent", base_url=settings.issuer, data={}).status_code == 400
    denied = browser.post(
        "/consent", base_url=settings.issuer, data={"csrf": csrf_value(consent), "decision": "deny"}
    )
    result = parse_qs(urlsplit(denied.location).query)
    assert result == {"error": ["access_denied"], "state": [params["state"]]}
    assert (
        browser.post(
            "/consent",
            base_url=settings.issuer,
            data={"csrf": csrf_value(consent), "decision": "allow"},
        ).status_code
        == 400
    )


def test_login_throttle_and_secure_cookies(lab):
    browser = lab["auth"].test_client()
    issuer = lab["settings"].issuer
    first = browser.get(
        "/authorize?" + urlencode(authorize_params(lab["settings"])), base_url=issuer
    )
    cookie = first.headers["Set-Cookie"]
    assert "Secure" in cookie and "HttpOnly" in cookie and "SameSite=Lax" in cookie
    assert "Domain=" not in cookie and cookie.startswith("__Host-")
    login = browser.get("/login", base_url=issuer)
    for _ in range(5):
        assert (
            browser.post(
                "/login",
                base_url=issuer,
                data={
                    "csrf": csrf_value(login),
                    "username": "student",
                    "password": "incorrect",
                },
            ).status_code
            == 200
        )
    response = browser.post(
        "/login",
        base_url=issuer,
        data={
            "csrf": csrf_value(login),
            "username": "student",
            "password": "incorrect",
        },
    )
    assert response.status_code == 429


def test_bearer_errors(lab):
    api = lab["api"].test_client()
    missing = api.get("/notes")
    assert missing.status_code == 401
    assert "error=" not in missing.headers["WWW-Authenticate"]
    assert api.get("/notes?access_token=forbidden").status_code == 400
    assert api.get("/notes", headers={"Authorization": "Bearer malformed"}).status_code == 401


def test_discovery_and_public_jwks(lab):
    browser = lab["auth"].test_client()
    metadata = browser.get("/.well-known/openid-configuration").json
    assert metadata["issuer"] == lab["settings"].issuer
    assert metadata["response_types_supported"] == ["code"]
    assert metadata["code_challenge_methods_supported"] == ["S256"]
    assert "userinfo_endpoint" not in metadata
    key = browser.get("/jwks").json["keys"][0]
    assert "d" not in key and "p" not in key and key["alg"] == "RS256"


@pytest.mark.parametrize("mutation", ["issuer", "audience", "expired", "signature", "algorithm"])
def test_api_rejects_token_mutations(lab, mutation):
    settings = lab["settings"]
    token = redeem(lab, issue(lab)).json["access_token"]
    claims = jwt.decode(token, options={"verify_signature": False})
    algorithm, key = "RS256", settings.private_key
    if mutation == "issuer":
        claims["iss"] = "https://attacker.test"
    elif mutation == "audience":
        claims["aud"] = "another-api"
    elif mutation == "expired":
        claims["exp"] = 1
    elif mutation == "algorithm":
        algorithm, key = "HS256", "test-only-key" * 4
    forged = jwt.encode(
        claims, key, algorithm=algorithm, headers={"kid": settings.kid, "typ": "at+jwt"}
    )
    if mutation == "signature":
        parts = forged.split(".")
        parts[2] = ("A" if parts[2][0] != "A" else "B") + parts[2][1:]
        forged = ".".join(parts)
    assert api_get(lab, forged).status_code == 401


def test_signing_failure_rolls_back_consumption(lab, monkeypatch):
    from authflow import authorization

    code = issue(lab)
    original = authorization.mint

    def fail(*args):
        raise RuntimeError("synthetic signing outage")

    monkeypatch.setattr(authorization, "mint", fail)
    lab["auth"].testing = False
    assert redeem(lab, code).status_code == 500
    with lab["sessions"]() as db:
        assert not db.get(Code, digest(code)).consumed
    monkeypatch.setattr(authorization, "mint", original)
    assert redeem(lab, code).status_code == 200
