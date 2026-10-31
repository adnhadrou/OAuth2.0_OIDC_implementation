import os
import re
from datetime import timedelta
from urllib.parse import parse_qs, urlencode, urlsplit

import pytest
from alembic import command
from alembic.config import Config
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import text
from sqlalchemy.engine import make_url

from authflow.authorization import create_app
from authflow.common import utcnow
from authflow.config import Settings
from authflow.models import Code, User, database
from authflow.resource import create_app as create_api
from authflow.security import TokenValidator, challenge, digest, opaque, passwords, public_jwk


@pytest.fixture(scope="session")
def settings():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return Settings(
        database_url=os.environ.get("TEST_DATABASE_URL", ""),
        issuer="https://auth.authflow.test:8443",
        client_origin="https://client.authflow.test:8444",
        api_origin="https://api.authflow.test:8445",
        private_key=key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ),
        public_key=key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        ),
        ca_bundle=".local/ca.pem",
        client_secrets={"demo-web": opaque(), "second-web": opaque()},
        login_password=opaque(),
    )


@pytest.fixture(scope="session")
def storage(settings):
    if not settings.database_url:
        pytest.skip("TEST_DATABASE_URL is not configured; PostgreSQL integration not executed")
    if make_url(settings.database_url).database != "authflow_test":
        pytest.fail("Refusing to reset a database other than authflow_test")
    old = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = settings.database_url
    try:
        command.upgrade(Config("alembic.ini"), "head")
    finally:
        if old is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = old
    engine, sessions = database(settings.database_url)
    yield engine, sessions
    engine.dispose()


@pytest.fixture
def lab(settings, storage):
    engine, sessions = storage
    with engine.begin() as connection:
        connection.execute(
            text("TRUNCATE TABLE authorization_codes, browser_sessions, login_throttles, users")
        )
    with sessions.begin() as db:
        db.add(
            User(
                id="student-001",
                username="student",
                password_hash=passwords.hash(settings.login_password),
            )
        )
    auth = create_app(settings)
    api = create_api(settings, TokenValidator(settings, {"keys": [public_jwk(settings)]}))
    auth.testing = api.testing = True
    yield {"auth": auth, "api": api, "settings": settings, "sessions": sessions}
    auth.extensions["engine"].dispose()
    api.extensions["engine"].dispose()


def csrf_value(response):
    return re.search(r'name="csrf" value="([^"]+)"', response.get_data(as_text=True))[1]


def authorize_params(settings, **overrides):
    return {
        "client_id": "demo-web",
        "redirect_uri": settings.client_origin + "/callback",
        "response_type": "code",
        "scope": "openid notes:read",
        "state": opaque(),
        "nonce": opaque(),
        "code_challenge": challenge("v" * 43),
        "code_challenge_method": "S256",
        **overrides,
    }


def issue(lab, **overrides):
    settings = lab["settings"]
    browser = lab["auth"].test_client()
    response = browser.get(
        "/authorize?" + urlencode(authorize_params(settings, **overrides)), base_url=settings.issuer
    )
    assert response.status_code == 303
    response = browser.get("/login", base_url=settings.issuer)
    response = browser.post(
        "/login",
        base_url=settings.issuer,
        data={
            "csrf": csrf_value(response),
            "username": "student",
            "password": settings.login_password,
        },
    )
    assert response.status_code == 303
    response = browser.get("/consent", base_url=settings.issuer)
    response = browser.post(
        "/consent",
        base_url=settings.issuer,
        data={"csrf": csrf_value(response), "decision": "allow"},
    )
    assert response.status_code == 303
    return parse_qs(urlsplit(response.location).query)["code"][0]


def redeem(lab, code, client="demo-web", **overrides):
    settings = lab["settings"]
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.client_origin + "/callback",
        "code_verifier": "v" * 43,
    }
    data.update(overrides)
    data = {k: v for k, v in data.items() if v is not None}
    return (
        lab["auth"]
        .test_client()
        .post(
            "/token",
            base_url=settings.issuer,
            data=data,
            auth=(client, settings.client_secrets[client]),
        )
    )


def expire_code(lab, code):
    with lab["sessions"].begin() as db:
        db.get(Code, digest(code)).expires_at = utcnow() - timedelta(seconds=1)
