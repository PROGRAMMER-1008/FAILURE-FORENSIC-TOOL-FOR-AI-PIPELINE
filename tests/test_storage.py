import pytest
from sqlalchemy import update
from ffv2.db import engine, jobs, metadata
from ffv2.models import Run
from ffv2.privacy import fingerprint
from ffv2.store import Conflict, LostLease, Store


@pytest.fixture
def store(tmp_path):
    eng = engine(f"sqlite:///{tmp_path / 'test.db'}")
    metadata.create_all(eng)
    yield Store(eng)
    eng.dispose()


def new_run(store):
    return store.enqueue(Run(source="synthetic", source_hash=fingerprint("synthetic")), "key")


def test_enqueue_idempotency(store):
    first = new_run(store)
    assert new_run(store).id == first.id
    with pytest.raises(Conflict):
        store.enqueue(Run(source="different", source_hash="other"), "key")


def test_restart_timestamp_and_fencing(store):
    run = new_run(store)
    first = store.claim("worker-a")
    run.status = "running"
    store.checkpoint(run, first, "running")
    created = run.created_at
    with store.engine.begin() as conn:
        conn.execute(update(jobs).values(lease_until="2000-01-01"))
    second = Store(store.engine).claim("worker-b")
    with pytest.raises(LostLease):
        store.checkpoint(run, first, "stale")
    run.created_at = "wrong"
    store.checkpoint(run, second, "recovered")
    assert store.get(run.id).created_at == created
    assert [e["sequence"] for e in store.event_list(run.id)] == [1, 2, 3]
