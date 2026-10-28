import asyncio

import httpx
import pytest
from sqlalchemy import update

from ffv2.api import create_app
from ffv2.db import owner_sessions
from ffv2.models import Run
from ffv2.settings import Settings
from ffv2.visitors import COOKIE, visitor
from ffv2.worker import SYNTHETIC_SOURCE, run_one

ORIGIN = "https://public.example"


def client(app):
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url=ORIGIN, headers={"Origin": ORIGIN}
    )


def public_settings(**kwargs):
    return Settings(mode="public", public_origin=ORIGIN, **kwargs)


@pytest.mark.enable_socket
def test_visitors_cannot_access_each_others_artifacts(store):
    legacy = store.enqueue(Run(source="Private owner document", source_hash="private"), "legacy")
    app = create_app(
        public_settings(visitor_daily_submissions=20, public_daily_submissions=100), store
    )

    async def scenario():
        async with client(app) as a, client(app) as b:
            for c in (a, b):
                r = await c.get("/api/v1/config")
                assert r.status_code == 200
                assert "HttpOnly" in r.headers["set-cookie"] and "Secure" in r.headers["set-cookie"]
                assert "no-store" in r.headers["cache-control"]
                assert r.json()["mode"] == "public"
                assert (await c.get("/api/v1/runs")).json()["items"] == []
                assert (await c.get(f"/api/v1/runs/{legacy.id}")).status_code == 404
            body = {"text": SYNTHETIC_SOURCE, "injected": True, "idempotency_key": "same-key"}
            ra = await a.post("/api/v1/runs", json=body)
            rb = await b.post("/api/v1/runs", json=body)
            assert ra.status_code == rb.status_code == 202
            aid, bid = ra.json()["id"], rb.json()["id"]
            assert aid != bid
            assert (await a.post("/api/v1/runs", json=body)).json()["id"] == aid
            assert visitor.get() is None
            # Worker has system scope, while every HTTP request has visitor scope.
            for _ in range(3):
                run_one(store, Settings())
            assert [r["id"] for r in (await a.get("/api/v1/runs")).json()["items"]] == [aid]
            assert sum(r["count"] for r in (await b.get("/api/v1/stats")).json()) == 1
            run = (await a.get(f"/api/v1/runs/{aid}")).json()
            review = {
                "idempotency_key": "review",
                "reviewer": "Visitor",
                "revision": run["revision"],
                "target_finding_revision": 1,
                "verdict": "no_issue",
                "origins": [],
            }
            replay = {"idempotency_key": "replay", "mode": "reexecute", "description": "Control"}
            for suffix in ["", "/export", "/events", "/reviews", "/comparison"]:
                assert (await b.get(f"/api/v1/runs/{aid}" + suffix)).status_code == 404
            for suffix, data in [("/cancel", {}), ("/reviews", review), ("/replays", replay)]:
                assert (await b.post(f"/api/v1/runs/{aid}" + suffix, json=data)).status_code == 404
            assert (await a.post(f"/api/v1/runs/{aid}/reviews", json=review)).status_code == 200
            cases = (await a.get("/api/v1/datasets")).json()
            assert len(cases) == 1
            assert (await b.get("/api/v1/datasets")).json() == []
            freeze = {"name": "My review", "case_ids": [cases[0]["id"]]}
            assert (await b.post("/api/v1/datasets/versions", json=freeze)).status_code == 404
            frozen = await a.post("/api/v1/datasets/versions", json=freeze)
            assert frozen.status_code == 201
            version = frozen.json()["id"]
            assert (await b.get("/api/v1/datasets/versions")).json() == []
            assert (await b.get(f"/api/v1/datasets/versions/{version}/export")).status_code == 404
            exp = await a.post(
                "/api/v1/experiments", json={"mode": "synthetic", "idempotency_key": "exp"}
            )
            assert exp.status_code == 201
            assert (await b.get("/api/v1/experiments")).json() == []
            assert (
                await b.get("/api/v1/experiments/" + exp.json()["id"] + "/results")
            ).status_code == 404
            assert (await b.get("/api/v1/metrics")).status_code == 404
            replayed = await a.post(f"/api/v1/runs/{aid}/replays", json=replay)
            assert replayed.status_code == 202
            assert (await b.get("/api/v1/runs/" + replayed.json()["id"])).status_code == 404
            assert (await a.get(f"/api/v1/runs/{aid}/export")).json()["run"]["id"] == aid
            # Concurrent contexts must not cross-contaminate results.
            responses = await asyncio.gather(*[c.get("/api/v1/runs") for c in [a, b] * 5])
            for i, response in enumerate(responses):
                ids = {r["id"] for r in response.json()["items"]}
                assert (bid in ids) == bool(i % 2)
                assert (aid in ids) != bool(i % 2)

    asyncio.run(scenario())


@pytest.mark.enable_socket
def test_public_expiry_csrf_forgery_and_shared_budget(store):
    app = create_app(
        public_settings(visitor_daily_submissions=1, public_daily_submissions=2), store
    )

    async def scenario():
        async with client(app) as a, client(app) as b, client(app) as c:
            body = {"text": "Invented document", "idempotency_key": "one"}
            assert (await a.post("/api/v1/runs", json=body)).status_code == 401
            for session in (a, b, c):
                assert (await session.get("/api/v1/config")).status_code == 200
            assert (
                await a.post("/api/v1/runs", json=body, headers={"Origin": "https://evil.example"})
            ).status_code == 403
            assert (await a.post("/api/v1/runs", json=body)).status_code == 202
            assert (await a.post("/api/v1/runs", json=body)).status_code == 429
            assert (await b.post("/api/v1/runs", json=body)).status_code == 202
            assert (
                await c.post("/api/v1/runs", json=body, headers={"X-Forwarded-For": "another-user"})
            ).status_code == 429
            assert (
                await c.get(
                    "/api/v1/runs",
                    headers={"Cookie": COOKIE + "=forged", "X-Auth-Request-User": "owner"},
                )
            ).status_code == 401
            with store.engine.begin() as conn:
                conn.execute(update(owner_sessions).values(expires=1))
            assert (await a.get("/api/v1/runs")).status_code == 401
            assert (await a.get("/api/v1/config")).status_code == 200
            assert (await a.get("/api/v1/runs")).json()["items"] == []

    asyncio.run(scenario())


def test_public_requires_https_origin_but_no_password():
    assert public_settings().owner_password_hash.get_secret_value() == ""
    with pytest.raises(ValueError):
        Settings(mode="public")
    with pytest.raises(ValueError):
        Settings(mode="public", public_origin="http://example.com")
