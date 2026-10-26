"""Opt-in disposable DB tests. Never point FF_TEST_DATABASE_URL at user data."""

import os
from concurrent.futures import ThreadPoolExecutor
import pytest
from sqlalchemy import update
from ffv2.db import engine, jobs, metadata
from ffv2.models import Run, uid
from ffv2.store import LostLease, Store
from ffv2.limits import reserve


@pytest.mark.postgres
@pytest.mark.enable_socket
def test_postgres_concurrent_claims_and_fence():
    url = os.environ.get("FF_TEST_DATABASE_URL")
    if not url:
        pytest.skip("FF_TEST_DATABASE_URL unset; requires disposable PostgreSQL database")
    eng = engine(url)
    metadata.create_all(eng)
    store = Store(eng)
    run = store.enqueue(
        Run(source="synthetic postgres", source_hash="fixture"), "pg-concurrency-" + uid()
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        claims = list(pool.map(store.claim, ["a", "b"]))
    winners = [c for c in claims if c]
    assert len(winners) == 1
    with eng.begin() as conn:
        conn.execute(update(jobs).where(jobs.c.run_id == run.id).values(lease_until="2000-01-01"))
    successor = store.claim("c")
    with pytest.raises(LostLease):
        store.checkpoint(run, winners[0], "late")
    run.status = "succeeded"
    store.checkpoint(run, successor, "succeeded", terminal=True)
    assert store.get(run.id).status == "succeeded"
    eng.dispose()


@pytest.mark.postgres
@pytest.mark.enable_socket
def test_postgres_shared_budget_is_atomic():
    url = os.environ.get("FF_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Requires disposable PostgreSQL")
    eng = engine(url)
    metadata.create_all(eng)
    scope = "pg-budget-" + uid()
    with ThreadPoolExecutor(max_workers=8) as pool:
        accepted = list(pool.map(lambda _: reserve(eng, scope, 7, 60), range(32)))
    assert sum(accepted) == 7
    eng.dispose()


@pytest.mark.postgres
@pytest.mark.enable_socket
def test_postgres_backup_restore_new_database(tmp_path):
    """Actual pg_dump/pg_restore; no mocks and never overwrite the source database."""
    import json
    import subprocess
    import sys
    from sqlalchemy import select
    from sqlalchemy.engine import make_url

    url = os.environ.get("FF_TEST_DATABASE_URL")
    container = os.environ.get("FF_PG_TEST_CONTAINER")
    if not url or not container:
        pytest.skip("Requires disposable PostgreSQL container for restore drill")
    source_url = make_url(url)
    eng = engine(url)
    metadata.create_all(eng)
    store = Store(eng)
    original = store.enqueue(
        Run(source="restore drill invented evidence", source_hash="fixture"), "restore-" + uid()
    )
    from ffv2.worker import run_one
    from ffv2.settings import Settings

    run_one(store, Settings())
    expected = store.get(original.id).model_dump(mode="json")
    dump = tmp_path / "backup.dump"
    restored_name = "ff_restore_" + uid().replace("-", "")
    base = [sys.executable, "-m", "scripts.postgres_backup"]
    common = [
        "--container",
        container,
        "--user",
        source_url.username or "postgres",
        "--file",
        str(dump),
    ]
    subprocess.run(
        base + ["backup", "--database", source_url.database] + common,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        base + ["restore-new", "--database", restored_name] + common,
        check=True,
        capture_output=True,
    )
    restored = engine(source_url.set(database=restored_name).render_as_string(hide_password=False))
    assert Store(restored).get(original.id).model_dump(mode="json") == expected
    for table in metadata.sorted_tables:
        with eng.connect() as left, restored.connect() as right:
            a = sorted(
                json.dumps(dict(row), sort_keys=True, default=str)
                for row in left.execute(select(table)).mappings()
            )
            b = sorted(
                json.dumps(dict(row), sort_keys=True, default=str)
                for row in right.execute(select(table)).mappings()
            )
            assert a == b, table.name
    # Refuse an existing destination. The restored application data must survive refusal.
    refused = subprocess.run(
        base + ["restore-new", "--database", restored_name] + common, capture_output=True
    )
    assert refused.returncode != 0
    assert Store(restored).get(original.id).model_dump(mode="json") == expected
    restored.dispose()
    eng.dispose()
