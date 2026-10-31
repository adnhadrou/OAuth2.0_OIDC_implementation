import base64
import hashlib
import re
import secrets
import time

import jwt
import requests
from argon2 import PasswordHasher
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from jwt import PyJWK

passwords = PasswordHasher()
VERIFIER = re.compile(r"[A-Za-z0-9._~-]{43,128}\Z")
CHALLENGE = re.compile(r"[A-Za-z0-9_-]{43}\Z")


def opaque():
    return secrets.token_urlsafe(32)


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def challenge(verifier):
    return (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest())
        .rstrip(b"=")
        .decode()
    )


def public_jwk(settings):
    result = jwt.algorithms.RSAAlgorithm.to_jwk(
        load_pem_public_key(settings.public_key), as_dict=True
    )
    return {**result, "kid": settings.kid, "use": "sig", "alg": "RS256"}


def mint(settings, code):
    now = int(time.time())
    common = {
        "iss": settings.issuer,
        "sub": code.user_id,
        "iat": now,
        "exp": now + settings.token_ttl,
    }
    access = jwt.encode(
        {
            **common,
            "aud": settings.api_origin,
            "client_id": code.client_id,
            "scope": code.scope,
            "jti": code.digest,
            "token_use": "access",
        },
        settings.private_key,
        algorithm="RS256",
        headers={"kid": settings.kid, "typ": "at+jwt"},
    )
    result = {
        "access_token": access,
        "token_type": "Bearer",
        "expires_in": settings.token_ttl,
        "scope": code.scope,
    }
    if "openid" in code.scope.split():
        claims = {**common, "aud": code.client_id, "nonce": code.nonce, "auth_time": code.auth_time}
        result["id_token"] = jwt.encode(
            claims,
            settings.private_key,
            algorithm="RS256",
            headers={"kid": settings.kid, "typ": "JWT"},
        )
    return result


class TokenValidator:
    """Fetch keys only from the configured issuer; never follow JWT jku/x5u."""

    def __init__(self, settings, jwks=None):
        self.settings = settings
        self.jwks = jwks
        self.loaded_at = 0

    def validate(self, token, kind, nonce=None):
        if not isinstance(token, str) or len(token) > 8192:
            raise jwt.InvalidTokenError("Invalid token size")
        header = jwt.get_unverified_header(token)
        expected_type = "at+jwt" if kind == "access" else "JWT"
        if (
            header.get("alg") != "RS256"
            or header.get("typ") != expected_type
            or any(k in header for k in ("jku", "x5u", "jwk", "crit"))
        ):
            raise jwt.InvalidTokenError("Unsupported token header")
        if self.jwks is None or (self.loaded_at and time.monotonic() - self.loaded_at > 300):
            response = requests.get(
                self.settings.issuer + "/jwks",
                timeout=5,
                verify=self.settings.ca_bundle,
                allow_redirects=False,
            )
            response.raise_for_status()
            self.jwks = response.json()
            self.loaded_at = time.monotonic()
        keys = [
            k
            for k in self.jwks["keys"]
            if k.get("kid") == header.get("kid")
            and k.get("alg") == "RS256"
            and k.get("use") == "sig"
        ]
        if len(keys) != 1:
            raise jwt.InvalidTokenError("Unknown signing key")
        required = ["iss", "sub", "aud", "iat", "exp"]
        required += ["jti", "client_id", "scope", "token_use"] if kind == "access" else ["nonce"]
        claims = jwt.decode(
            token,
            PyJWK.from_dict(keys[0]).key,
            algorithms=["RS256"],
            issuer=self.settings.issuer,
            audience=self.settings.api_origin if kind == "access" else "demo-web",
            options={"require": required, "strict_aud": True},
        )
        if kind == "access":
            if claims["token_use"] != "access" or not isinstance(claims["scope"], str):
                raise jwt.InvalidTokenError("Invalid access token")
        elif (
            not isinstance(nonce, str)
            or not isinstance(claims["nonce"], str)
            or not secrets.compare_digest(claims["nonce"].encode(), nonce.encode())
        ):
            raise jwt.InvalidTokenError("Nonce mismatch")
        return claims
