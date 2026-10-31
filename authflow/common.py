import secrets
from datetime import UTC, datetime, timedelta

from flask import Flask, abort, g, request
from sqlalchemy import select

from .models import BrowserSession, database
from .security import digest, opaque


def utcnow():
    return datetime.now(UTC)


def app_base(service, settings):
    app = Flask(__name__)
    app.config.update(MAX_CONTENT_LENGTH=16384, MAX_FORM_PARTS=32)
    engine, sessions = database(settings.database_url)
    app.extensions.update(engine=engine, sessions=sessions, settings=settings)
    cookie_name = "__Host-authflow-" + service

    @app.before_request
    def begin():
        g.db = sessions()
        g.browser = None
        g.cookie = None
        # Protocol and resource calls never need a browser session.
        browser_route = service == "client" or (
            service == "auth" and request.path in ("/authorize", "/login", "/consent")
        )
        if not browser_route:
            return
        raw = request.cookies.get(cookie_name, "")
        if raw and len(raw) <= 128:
            row = g.db.scalar(
                select(BrowserSession)
                .where(BrowserSession.digest == digest(raw), BrowserSession.service == service)
                .with_for_update()
            )
            if row and row.expires_at > utcnow():
                g.browser = row
            elif row:
                g.db.delete(row)
                g.db.flush()
        if g.browser is None:
            new_browser(service, settings)

    @app.after_request
    def finish(response):
        # Commit before returning anything; token delivery cannot precede consumption.
        if getattr(g, "db", None):
            if response.status_code >= 500:
                g.db.rollback()
            else:
                g.db.commit()
        if getattr(g, "cookie", None):
            response.set_cookie(
                cookie_name,
                g.cookie,
                secure=True,
                httponly=True,
                samesite="Lax",
                path="/",
                max_age=settings.session_ttl,
            )
        response.headers.update(
            {
                "Cache-Control": "no-store",
                "Pragma": "no-cache",
                "Referrer-Policy": "no-referrer",
                "X-Content-Type-Options": "nosniff",
                "Content-Security-Policy": "default-src 'none'; style-src 'self'; "
                f"form-action 'self' {settings.issuer} {settings.client_origin}; "
                "frame-ancestors 'none'; base-uri 'none'",
                "Strict-Transport-Security": "max-age=86400",
            }
        )
        return response

    @app.teardown_request
    def close(error):
        if getattr(g, "db", None):
            g.db.rollback()
            g.db.close()

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app


def new_browser(service, settings, data=None):
    if getattr(g, "browser", None) is not None:
        g.db.delete(g.browser)
        g.db.flush()
    raw = opaque()
    g.browser = BrowserSession(
        digest=digest(raw),
        service=service,
        data={**(data or {}), "csrf": opaque()},
        expires_at=utcnow() + timedelta(seconds=settings.session_ttl),
    )
    g.db.add(g.browser)
    g.cookie = raw


def update_browser(**values):
    g.browser.data = {**g.browser.data, **values}


def csrf():
    values = request.form.getlist("csrf")
    expected = g.browser.data.get("csrf", "")
    if (
        len(values) != 1
        or not expected
        or not secrets.compare_digest(values[0].encode(), expected.encode())
    ):
        abort(400, "Invalid form transaction")
