import secrets
import time
from urllib.parse import urlencode

import jwt
import requests
from flask import g, redirect, render_template, request

from .common import app_base, csrf, new_browser, update_browser
from .security import TokenValidator, challenge, opaque


def create_app(settings, validator=None, http=None):
    app = app_base("client", settings)
    validator = validator or TokenValidator(settings)
    http = http or requests.Session()

    def page(message, status=400):
        return render_template("message.html", message=message), status

    @app.get("/")
    def home():
        return render_template(
            "home.html", csrf=g.browser.data["csrf"], subject=g.browser.data.get("subject")
        )

    @app.post("/start")
    def start():
        csrf()
        state, nonce, verifier = opaque(), opaque(), opaque()
        update_browser(
            transaction={
                "state": state,
                "nonce": nonce,
                "verifier": verifier,
                "expires": int(time.time()) + 300,
            }
        )
        return redirect(
            settings.issuer
            + "/authorize?"
            + urlencode(
                {
                    "client_id": "demo-web",
                    "redirect_uri": settings.client_origin + "/callback",
                    "response_type": "code",
                    "scope": "openid notes:read",
                    "state": state,
                    "nonce": nonce,
                    "code_challenge": challenge(verifier),
                    "code_challenge_method": "S256",
                }
            ),
            code=303,
        )

    @app.get("/callback")
    def callback():
        transaction = g.browser.data.get("transaction")
        # A callback consumes the browser transaction, including on failure.
        update_browser(transaction=None)
        state = request.args.get("state", "")
        if (
            not transaction
            or transaction["expires"] < time.time()
            or any(len(v) != 1 for _, v in request.args.lists())
            or not secrets.compare_digest(state.encode(), transaction["state"].encode())
        ):
            return page("Login transaction rejected. Start again.")
        if "error" in request.args:
            return page("Authorization was not granted.")
        if not request.args.get("code"):
            return page("Missing authorization code.")
        try:
            response = http.post(
                settings.issuer + "/token",
                data={
                    "grant_type": "authorization_code",
                    "code": request.args["code"],
                    "redirect_uri": settings.client_origin + "/callback",
                    "code_verifier": transaction["verifier"],
                },
                auth=("demo-web", settings.client_secrets["demo-web"]),
                timeout=5,
                verify=settings.ca_bundle,
                allow_redirects=False,
            )
            response.raise_for_status()
            tokens = response.json()
            claims = validator.validate(tokens["id_token"], "id", transaction["nonce"])
            if tokens.get("token_type", "").lower() != "bearer":
                raise ValueError("Unsupported token type")
        except (requests.RequestException, jwt.PyJWTError, KeyError, ValueError, TypeError):
            return page("Token exchange or ID token validation failed.")
        new_browser("client", settings, {"tokens": tokens, "subject": claims["sub"]})
        return redirect("/", code=303)

    @app.post("/notes")
    def notes():
        csrf()
        tokens = g.browser.data.get("tokens")
        if not tokens:
            return page("Sign in first.", 401)
        try:
            response = http.get(
                settings.api_origin + "/notes",
                headers={"Authorization": "Bearer " + tokens["access_token"]},
                verify=settings.ca_bundle,
                timeout=5,
                allow_redirects=False,
            )
            response.raise_for_status()
            notes = response.json()["notes"]
        except (requests.RequestException, KeyError, ValueError):
            return page("API access failed. The grant may have expired or been revoked.", 403)
        return render_template("notes.html", notes=notes)

    @app.post("/clear-session")
    def clear_session():
        csrf()
        new_browser("client", settings)
        return redirect("/", code=303)

    return app
