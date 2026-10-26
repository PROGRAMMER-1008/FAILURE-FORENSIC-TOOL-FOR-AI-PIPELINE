import asyncio
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import update

from ffv2.api import create_app
from ffv2.auth import COOKIE, password_hash
from ffv2.db import owner_sessions
from ffv2.limits import BudgetedProvider, reserve
from ffv2.providers import FakeProvider, execute
from ffv2.settings import Settings
from tests.test_api import request


def hosted(**overrides):
    return Settings(
        mode="hosted",
        public_origin="https://forensics.example",
        owner_password_hash=password_hash("test-only-owner-password"),
        **overrides,
    )


def test_hosted_configuration_fails_closed():
    with pytest.raises(ValueError):
        Settings(mode="hosted")
    with pytest.raises(ValueError):
        Settings(mode="hosted", public_origin="http://example.com", owner_password_hash="bad")
    assert Settings(database_url="postgres://user@db/app").database_url.startswith(
        "postgresql+psycopg://"
    )


@pytest.mark.enable_socket
def test_hosted_sessions_csrf_logout_expiry_and_rotation(store):
    settings = hosted()
    app = create_app(settings, store)

    async def scenario():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url=settings.public_origin
        ) as client:
            assert (await client.get("/")).status_code == 303
            assert (
                await client.get("/api/v1/runs", headers={"x-auth-request-user": "owner"})
            ).status_code == 401
            assert (await client.get("/auth/login")).status_code == 200
            body = {"password": "test-only-owner-password"}
            assert (await client.post("/auth/login", data=body)).status_code == 403
            headers = {"Origin": settings.public_origin}
            assert (
                await client.post(
                    "/auth/login", data={"password": "incorrect-password"}, headers=headers
                )
            ).status_code == 401
            login = await client.post("/auth/login", data=body, headers=headers)
            assert login.status_code == 303
            cookie = login.headers["set-cookie"]
            assert "HttpOnly" in cookie and "Secure" in cookie and "SameSite=strict" in cookie
            old_token = client.cookies.get(COOKIE)
            assert (await client.get("/api/v1/runs")).status_code == 200
            assert (
                await client.post(
                    "/api/v1/runs", json={}, headers={"Origin": "https://attacker.example"}
                )
            ).status_code == 403
            assert (await client.post("/auth/logout", headers=headers)).status_code == 303
            assert (
                await client.get("/api/v1/runs", headers={"Cookie": f"{COOKIE}={old_token}"})
            ).status_code == 401
            await client.post("/auth/login", data=body, headers=headers)
            with store.engine.begin() as conn:
                conn.execute(update(owner_sessions).values(expires=1))
            assert (await client.get("/api/v1/runs")).status_code == 401
            await client.post("/auth/login", data=body, headers=headers)
            settings.owner_password_hash = SecretStr(password_hash("new-test-only-password"))
            assert (await client.get("/api/v1/runs")).status_code == 401

    asyncio.run(scenario())


@pytest.mark.enable_socket
def test_login_limit_shared_across_instances(store):
    settings = hosted()
    apps = [create_app(settings, store), create_app(settings, store)]
    for i in range(10):
        response = request(
            apps[i % 2],
            "POST",
            "/auth/login",
            data={"password": "incorrect-password"},
            headers={"Origin": settings.public_origin},
        )
        assert response.status_code == 401
    assert (
        request(
            apps[1],
            "POST",
            "/auth/login",
            data={"password": "test-only-owner-password"},
            headers={"Origin": settings.public_origin},
        ).status_code
        == 401
    )


@pytest.mark.enable_socket
def test_mutation_limit_survives_api_restart(store):
    for i in range(2):
        app = create_app(Settings(mutations_per_minute=2), store)
        assert request(app, "POST", "/api/v1/runs", json={}).status_code == 422
    app = create_app(Settings(mutations_per_minute=2), store)
    assert request(app, "POST", "/api/v1/runs", json={}).status_code == 429


def test_atomic_budget_and_window_reset(store):
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(
            pool.map(lambda _: reserve(store.engine, "concurrent", 5, 60, at=120), range(24))
        )
    assert sum(results) == 5
    assert reserve(store.engine, "concurrent", 5, 60, at=180)


def test_provider_budget_blocks_before_call(store):
    provider = BudgetedProvider(FakeProvider(), store.engine, 1)
    assert execute(provider, "extract", {}).status == "succeeded"
    assert execute(provider, "extract", {}).error == "budget_exceeded"
