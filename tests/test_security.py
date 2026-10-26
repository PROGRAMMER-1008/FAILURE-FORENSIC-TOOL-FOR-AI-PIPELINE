import json
import pytest
from ffv2.models import Run
from ffv2.privacy import redact
from ffv2.settings import Settings
from ffv2.api import create_app
from tests.test_api import request


def test_secret_canary_never_persisted(store):
    canary = "sk-syntheticCanaryNotARealSecret123"
    run = store.enqueue(
        Run(
            source=f"Authorization: Bearer {canary}",
            source_hash="fixture",
            config={"api_key": canary},
        ),
        "secret-canary",
    )
    assert canary not in store.get(run.id).model_dump_json()
    assert canary not in json.dumps(redact({"output": canary, "password": canary}))


@pytest.mark.enable_socket
def test_private_mode_fail_closed_and_identity_boundary(store):
    with pytest.raises(ValueError):
        Settings(mode="private")
    app = create_app(
        Settings(
            mode="private", trusted_proxy_ips=["127.0.0.1"], authorized_subject="owner-subject"
        ),
        store,
    )
    assert request(app, "GET", "/api/v1/runs").status_code == 403
    assert (
        request(
            app, "GET", "/api/v1/runs", headers={"x-auth-request-user": "other-user"}
        ).status_code
        == 403
    )
    assert (
        request(
            app, "GET", "/api/v1/runs", headers={"x-auth-request-user": "owner-subject"}
        ).status_code
        == 200
    )
    untrusted = create_app(
        Settings(
            mode="private", trusted_proxy_ips=["192.0.2.1"], authorized_subject="owner-subject"
        ),
        store,
    )
    assert (
        request(
            untrusted, "GET", "/api/v1/runs", headers={"x-auth-request-user": "owner-subject"}
        ).status_code
        == 401
    )
