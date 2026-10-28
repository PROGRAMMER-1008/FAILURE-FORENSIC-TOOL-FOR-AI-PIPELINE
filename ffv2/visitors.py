"""Anonymous browser access and request-local ownership; never trust client owner IDs."""

import asyncio
import secrets
import time
from contextvars import ContextVar

from fastapi.responses import JSONResponse
from sqlalchemy import delete, insert

from ffv2.auth import digest, session_valid
from ffv2.db import owner_sessions, runs
from ffv2.limits import reserve

visitor: ContextVar[str | None] = ContextVar("visitor", default=None)
COOKIE = "__Host-ff_visitor"
REVISION = "public-visitor-v1"


def run_scope():
    identity = visitor.get()
    return (
        True if identity is None else runs.c.payload["config"]["visitor_id"].as_string() == identity
    )


def document_scope(table):
    identity = visitor.get()
    return True if identity is None else table.c.payload["visitor_id"].as_string() == identity


async def public_boundary(request, settings, eng, call_next):
    path = request.url.path
    if not path.startswith("/api/"):
        if path.startswith("/auth/"):
            return JSONResponse({"error": "not_found"}, 404)
        return await call_next(request)
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        if request.headers.get("origin") != settings.public_origin:
            return JSONResponse({"error": "cross_origin_denied"}, 403)
    if path == "/api/v1/metrics":
        return JSONResponse({"error": "not_found"}, 404)
    token = request.cookies.get(COOKIE, "")
    valid = (
        bool(token)
        and len(token) <= 100
        and await asyncio.to_thread(session_valid, eng, token, REVISION)
    )
    fresh = False
    if not valid:
        if path != "/api/v1/config" or request.method != "GET":
            return JSONResponse(
                {
                    "error": "visitor_session_expired",
                    "detail": "Refresh to start a new visitor session.",
                },
                401,
            )
        # Global budget cannot be bypassed by clearing cookies or forging proxy/IP headers.
        if not await asyncio.to_thread(reserve, eng, "public-sessions", 200, 3600):
            return JSONResponse({"error": "Visitor capacity reached. Please try again later."}, 429)
        token = secrets.token_urlsafe(32)

        def save():
            with eng.begin() as conn:
                conn.execute(
                    delete(owner_sessions).where(owner_sessions.c.expires <= int(time.time()))
                )
                conn.execute(
                    insert(owner_sessions).values(
                        id=digest(token),
                        expires=int(time.time()) + settings.visitor_session_seconds,
                        revision=REVISION,
                    )
                )

        await asyncio.to_thread(save)
        fresh = True
    identity = digest(token)
    if request.method == "POST" and (
        path in {"/api/v1/runs", "/api/v1/uploads", "/api/v1/experiments"}
        or path.endswith("/replays")
    ):
        for scope, limit in [
            ("visitor-submissions-" + identity, settings.visitor_daily_submissions),
            ("public-submissions", settings.public_daily_submissions),
        ]:
            if not await asyncio.to_thread(reserve, eng, scope, limit, 86400):
                return JSONResponse(
                    {"error": "Daily investigation allowance reached. Try again tomorrow (UTC)."},
                    429,
                )
    context = visitor.set(identity)
    try:
        response = await call_next(request)
    finally:
        visitor.reset(context)
    if fresh:
        response.set_cookie(
            COOKIE,
            token,
            max_age=settings.visitor_session_seconds,
            secure=True,
            httponly=True,
            samesite="strict",
            path="/",
        )
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Vary"] = "Cookie"
    return response
