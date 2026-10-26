"""Single-owner hosted sessions. No shared-password public multi-user workspace."""

import asyncio
import hashlib
import hmac
import secrets
import time
from urllib.parse import parse_qs

from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import delete, insert, select

from ffv2.db import owner_sessions
from ffv2.limits import reserve

COOKIE = "__Host-ff_session"


def password_hash(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=5)
    return "scrypt$" + salt.hex() + "$" + digest.hex()


def valid_hash(value: str) -> bool:
    try:
        scheme, salt, digest = value.split("$")
        return (
            scheme == "scrypt"
            and len(bytes.fromhex(salt)) == 16
            and len(bytes.fromhex(digest)) == 64
        )
    except ValueError:
        return False


def verify(password: str, encoded: str) -> bool:
    if not valid_hash(encoded) or not 12 <= len(password) <= 256:
        return False
    return hmac.compare_digest(
        password_hash(password, bytes.fromhex(encoded.split("$")[1])), encoded
    )


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def login_page(error: bool = False, logout: bool = False) -> HTMLResponse:
    heading = "Sign out" if logout else "Sign in to your workspace"
    form = (
        '<form method="post" action="/auth/logout"><button>Sign out</button></form>'
        if logout
        else '<form method="post" action="/auth/login"><label for="password">Workspace password</label>'
        '<input id="password" name="password" type="password" autocomplete="current-password" minlength="12" maxlength="256" required>'
        "<button>Sign in</button></form>"
    )
    message = (
        '<p role="alert">Sign-in unsuccessful. Check your password or try again later.</p>'
        if error
        else ""
    )
    response = HTMLResponse(
        '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>Failure Forensics — Workspace sign-in</title><style>"
        "body{margin:0;background:#0c1021;color:#edf0ff;font:16px system-ui;display:grid;place-items:center;min-height:100vh}"
        "main{box-sizing:border-box;width:min(420px,calc(100% - 32px));padding:32px;background:#181d34;border:1px solid #454365;border-radius:20px}"
        "h1{font-size:26px}p{line-height:1.6}label,input,button{display:block;width:100%;box-sizing:border-box}"
        "input,button{padding:14px;border-radius:8px;margin-top:12px;font:inherit}input{background:#0c1021;color:white;border:1px solid #aaa}"
        "button{background:#c5b0ff;color:#19122d;border:0;cursor:pointer;font-weight:700}a{color:#c5b0ff}"
        "</style></head><body><main><p>FAILURE FORENSICS</p><h1>" + heading + "</h1>"
        "<p>This is a private, single-owner workspace. Only sign in if you are its owner.</p>"
        + message
        + form
        + "</main></body></html>",
        status_code=401 if error else 200,
    )
    response.headers.update(
        {
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'",
            "Referrer-Policy": "same-origin",
        }
    )
    return response


def session_valid(eng, token: str, revision: str) -> bool:
    with eng.connect() as conn:
        return (
            conn.execute(
                select(owner_sessions.c.id).where(
                    owner_sessions.c.id == digest(token),
                    owner_sessions.c.expires > int(time.time()),
                    owner_sessions.c.revision == revision,
                )
            ).first()
            is not None
        )


async def gate(request, settings, eng):
    """Return a response for auth routes/denials, None for an authenticated request."""
    path = request.url.path
    if path == "/health/live" or path == "/health/ready":
        return None  # Health responses contain no document or configuration values.
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        if request.headers.get("origin") != settings.public_origin:
            return JSONResponse({"error": "cross_origin_denied"}, 403)
    encoded = settings.owner_password_hash.get_secret_value()
    revision = digest(encoded)
    if path == "/auth/login":
        if request.method == "GET":
            return login_page()
        if request.method != "POST":
            return JSONResponse({"error": "method_not_allowed"}, 405)
        # Global DB-backed limit cannot be bypassed with spoofed forwarding headers.
        if not await asyncio.to_thread(reserve, eng, "owner-login", 10, 300):
            return login_page(error=True)
        body = await request.body()
        if len(body) > 2048:
            return login_page(error=True)
        password = parse_qs(body.decode("utf-8", errors="replace")).get("password", [""])[0]
        if not await asyncio.to_thread(verify, password, encoded):
            return login_page(error=True)
        token = secrets.token_urlsafe(32)
        expires = int(time.time()) + settings.session_seconds

        def save():
            with eng.begin() as conn:
                conn.execute(
                    delete(owner_sessions).where(owner_sessions.c.expires <= int(time.time()))
                )
                conn.execute(
                    insert(owner_sessions).values(
                        id=digest(token), expires=expires, revision=revision
                    )
                )

        await asyncio.to_thread(save)
        response = RedirectResponse("/", status_code=303)
        response.set_cookie(
            COOKIE,
            token,
            max_age=settings.session_seconds,
            secure=True,
            httponly=True,
            samesite="strict",
            path="/",
        )
        response.headers["Cache-Control"] = "no-store"
        return response
    token = request.cookies.get(COOKIE, "")
    if (
        not token
        or len(token) > 100
        or not await asyncio.to_thread(session_valid, eng, token, revision)
    ):
        if path.startswith("/api/"):
            return JSONResponse({"error": "sign_in_required"}, 401)
        return RedirectResponse("/auth/login", status_code=303)
    if path == "/auth/logout":
        if request.method == "GET":
            return login_page(logout=True)
        if request.method != "POST":
            return JSONResponse({"error": "method_not_allowed"}, 405)

        def remove():
            with eng.begin() as conn:
                conn.execute(delete(owner_sessions).where(owner_sessions.c.id == digest(token)))

        await asyncio.to_thread(remove)
        response = RedirectResponse("/auth/login", status_code=303)
        response.delete_cookie(COOKIE, secure=True, httponly=True, samesite="strict", path="/")
        return response
    return None


if __name__ == "__main__":
    from getpass import getpass

    password = getpass("Choose a workspace password (12–256 characters): ")
    if not 12 <= len(password) <= 256 or password != getpass("Repeat password: "):
        raise SystemExit("Passwords must match and contain 12–256 characters.")
    print(
        "Set FF_OWNER_PASSWORD_HASH in your host's secret settings to this value (do not commit):"
    )
    print(password_hash(password))
