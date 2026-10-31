import time
from types import SimpleNamespace

import jwt
import pytest
from hypothesis import given
from hypothesis import strategies as st

from authflow.security import TokenValidator, challenge, mint, public_jwk


@pytest.fixture
def validator(settings):
    return TokenValidator(settings, {"keys": [public_jwk(settings)]})


def signed(settings, kind="id", **overrides):
    claims = {
        "iss": settings.issuer,
        "sub": "student-001",
        "aud": "demo-web",
        "iat": int(time.time()),
        "exp": int(time.time()) + 60,
        "nonce": "n" * 32,
    }
    if kind == "access":
        claims.update(
            aud=settings.api_origin,
            scope="notes:read",
            jti="test-grant",
            token_use="access",
            client_id="demo-web",
        )
    claims.update(overrides)
    return jwt.encode(
        claims,
        settings.private_key,
        algorithm="RS256",
        headers={"kid": settings.kid, "typ": "JWT" if kind == "id" else "at+jwt"},
    )


@pytest.mark.parametrize("kind", ["id", "access"])
@pytest.mark.parametrize(
    "field,value",
    [
        ("iss", "https://evil.test"),
        ("aud", "wrong-audience"),
        ("exp", 1),
        ("iat", 9999999999),
        ("sub", None),
    ],
)
def test_token_claim_rejections(settings, validator, kind, field, value):
    with pytest.raises(jwt.PyJWTError):
        validator.validate(signed(settings, kind, **{field: value}), kind, "n" * 32)


def test_nonce_validation(settings, validator):
    token = signed(settings)
    with pytest.raises(jwt.PyJWTError):
        validator.validate(token, "id", "different")
    assert validator.validate(token, "id", "n" * 32)["sub"] == "student-001"


@pytest.mark.parametrize("alg", ["none", "HS256", "RS512"])
def test_unexpected_algorithm(settings, validator, alg):
    key = None if alg == "none" else ("a" * 32 if alg == "HS256" else settings.private_key)
    token = jwt.encode(
        {"sub": "forged"}, key, algorithm=alg, headers={"kid": settings.kid, "typ": "JWT"}
    )
    with pytest.raises(jwt.PyJWTError):
        validator.validate(token, "id", "n" * 32)


def test_invalid_signature(settings, validator):
    token = signed(settings)
    header, payload, signature = token.split(".")
    signature = ("A" if signature[0] != "A" else "B") + signature[1:]
    with pytest.raises(jwt.PyJWTError):
        validator.validate(".".join([header, payload, signature]), "id", "n" * 32)


@pytest.mark.parametrize(
    "header",
    [
        {"jku": "https://evil.test/keys"},
        {"x5u": "https://evil.test/cert"},
        {"kid": "unregistered"},
        {"crit": ["unknown"]},
    ],
)
def test_untrusted_key_headers(settings, validator, header):
    token = jwt.encode(
        {},
        settings.private_key,
        algorithm="RS256",
        headers={"kid": settings.kid, "typ": "JWT", **header},
    )
    with pytest.raises(jwt.PyJWTError):
        validator.validate(token, "id", "n" * 32)


def test_cross_token_type_rejected(settings, validator):
    with pytest.raises(jwt.PyJWTError):
        validator.validate(signed(settings), "access")
    with pytest.raises(jwt.PyJWTError):
        validator.validate(signed(settings, "access"), "id", "n" * 32)


def test_minted_tokens_have_distinct_audiences(settings, validator):
    code = SimpleNamespace(
        user_id="student-001",
        client_id="demo-web",
        digest="code-hash",
        scope="openid notes:read",
        nonce="n" * 32,
        auth_time=int(time.time()),
    )
    tokens = mint(settings, code)
    assert validator.validate(tokens["id_token"], "id", "n" * 32)["aud"] == "demo-web"
    assert validator.validate(tokens["access_token"], "access")["aud"] == settings.api_origin


def test_rfc7636_vector():
    assert challenge("dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk") == (
        "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
    )


@given(
    st.text(
        alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~",
        min_size=43,
        max_size=128,
    )
)
def test_pkce_mutation_changes_challenge(verifier):
    mutated = ("A" if verifier[0] != "A" else "B") + verifier[1:]
    assert challenge(verifier) != challenge(mutated)
    assert len(challenge(verifier)) == 43
