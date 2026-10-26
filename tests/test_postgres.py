"""Opt-in disposable DB tests. Never point FF_TEST_DATABASE_URL at user data."""

import os
from concurrent.futures import ThreadPoolExecutor
import pytest
from sqlalchemy import update
from ffv2.db import engine, jobs, metadata
from ffv2.models import Run, uid
from ffv2.store import LostLease, Store


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
