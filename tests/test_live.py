"""Real HTTPS and browser tests against the running Compose environment."""

import json
import os
import re
import time
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
import requests
from authlib.integrations.requests_client import OAuth2Session
from authlib.oidc.core import CodeIDToken
from joserfc import jwt as independent_jwt
from joserfc.jwk import KeySet
from playwright.sync_api import sync_playwright

from authflow.security import opaque

pytestmark = [
    pytest.mark.browser,
    pytest.mark.skipif(
        os.environ.get("RUN_BROWSER") != "1",
        reason="Set RUN_BROWSER=1 with the trusted HTTPS stack available",
    ),
]
ISSUER = "https://auth.authflow.test:8443"
CLIENT = "https://client.authflow.test:8444"
API = "https://api.authflow.test:8445"
CA = ".local/ca.pem"


def browser_args():
    args = ["--no-sandbox"]
    if os.environ.get("LAB_BROWSER_HOST_RULES"):
        args.append("--host-resolver-rules=" + os.environ["LAB_BROWSER_HOST_RULES"])
    return args


@pytest.fixture(scope="module")
def live():
    last_error = "No healthy response"
    for _ in range(40):
        try:
            responses = [
                requests.get(origin + "/health", verify=CA, timeout=2)
                for origin in (ISSUER, CLIENT, API)
            ]
            if all(response.status_code == 200 for response in responses):
                break
        except requests.RequestException as exc:
            last_error = str(exc)
            time.sleep(0.5)
    else:
        pytest.fail("Trusted HTTPS stack is unavailable: " + last_error)
    return json.loads(Path(".local/secrets.json").read_text())


def test_https_requires_trusted_ca(live):
    import certifi

    with pytest.raises(requests.exceptions.SSLError):
        requests.get(ISSUER + "/jwks", verify=certifi.where(), timeout=5)
    assert requests.get(ISSUER + "/jwks", verify=CA, timeout=5).status_code == 200


def test_browser_login_callback_api(live):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(args=browser_args())
        context = browser.new_context()
        page = context.new_page()
        page.goto(CLIENT)
        page.get_by_role("button", name="Start secure sign-in").click()
        page.get_by_label("Username").fill("student")
        page.get_by_label("Password").fill(live["password"])
        page.get_by_role("button", name="Sign in", exact=True).click()
        page.get_by_role("button", name="Allow access").click()
        page.wait_for_url(CLIENT + "/")
        assert page.get_by_text("student-001", exact=True).count() == 1
        assert page.evaluate("Object.keys(localStorage).length") == 0
        assert "access_token" not in page.content()
        assert page.evaluate("document.cookie") == ""
        page.get_by_role("button", name="Read protected notes").click()
        assert page.get_by_text("Synthetic note: the API checked notes:read.").count() == 1
        for cookie in context.cookies():
            assert cookie["secure"] and cookie["httpOnly"] and cookie["sameSite"] == "Lax"
        browser.close()


def test_browser_callback_state_attack(live):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(args=browser_args())
        page = browser.new_page()
        page.goto(CLIENT)
        page.get_by_role("button", name="Start secure sign-in").click()
        page.goto(CLIENT + "/callback?state=attacker&code=synthetic-invalid-code")
        assert page.get_by_role("alert").inner_text() == "Login transaction rejected. Start again."
        browser.close()


def test_independent_authlib_oidc_client(live):
    metadata = requests.get(ISSUER + "/.well-known/openid-configuration", verify=CA).json()
    assert metadata["issuer"] == ISSUER
    nonce, verifier = opaque(), opaque()
    oauth = OAuth2Session(
        "demo-web",
        live["clients"]["demo-web"],
        scope="openid notes:read",
        redirect_uri=CLIENT + "/callback",
        code_challenge_method="S256",
        token_endpoint_auth_method="client_secret_basic",
    )
    oauth.verify = CA
    url, state = oauth.create_authorization_url(
        metadata["authorization_endpoint"], nonce=nonce, code_verifier=verifier
    )
    user = requests.Session()
    user.verify = CA
    login = user.get(url, timeout=5)
    csrf = re.search(r'name="csrf" value="([^"]+)"', login.text)[1]
    consent = user.post(
        ISSUER + "/login",
        data={"csrf": csrf, "username": "student", "password": live["password"]},
        timeout=5,
    )
    csrf = re.search(r'name="csrf" value="([^"]+)"', consent.text)[1]
    result = user.post(
        ISSUER + "/consent",
        data={"csrf": csrf, "decision": "allow"},
        allow_redirects=False,
        timeout=5,
    )
    callback = result.headers["Location"]
    assert parse_qs(urlsplit(callback).query)["state"] == [state]
    tokens = oauth.fetch_token(
        metadata["token_endpoint"],
        authorization_response=callback,
        code_verifier=verifier,
        timeout=5,
    )
    keys = requests.get(metadata["jwks_uri"], verify=CA, timeout=5).json()
    decoded = independent_jwt.decode(
        tokens["id_token"], KeySet.import_key_set(keys), algorithms=["RS256"]
    )
    claims = CodeIDToken(
        decoded.claims,
        decoded.header,
        options={
            "iss": {"essential": True, "value": ISSUER},
            "aud": {"essential": True, "value": "demo-web"},
        },
        params={"nonce": nonce, "client_id": "demo-web"},
    )
    claims.validate()
    assert claims["sub"] == "student-001"
    assert (
        requests.get(
            API + "/notes",
            headers={"Authorization": "Bearer " + tokens["access_token"]},
            verify=CA,
            timeout=5,
        ).status_code
        == 200
    )
