from ffv2.models import Run, ReviewInput
from ffv2.operations import backup_sqlite, delete_run
from ffv2.db import engine
from ffv2.store import Missing, Store
from ffv2.store import Conflict
from ffv2.worker import run_one, SYNTHETIC_SOURCE
from ffv2.settings import Settings
from ffv2.datasets import freeze, FreezeRequest
from ffv2.db import cases, datasets
from sqlalchemy import select
import pytest


def test_backup_restore_and_deletion(store, tmp_path):
    run = store.enqueue(Run(source="Synthetic backup", source_hash="fixture"), "backup")
    store.cancel(run.id)
    backup = tmp_path / "backup.db"
    backup_sqlite(tmp_path / "test.db", backup)
    restored = tmp_path / "restored.db"
    backup_sqlite(backup, restored)
    eng = engine(f"sqlite:///{restored}")
    assert Store(eng).get(run.id).status == "cancelled"
    eng.dispose()
    delete_run(store, run.id)
    with pytest.raises(Missing):
        store.get(run.id)


def test_privacy_delete_requires_explicit_snapshot_invalidation(store):
    run = store.enqueue(Run(source=SYNTHETIC_SOURCE, source_hash="fixture"), "privacy-delete")
    run_one(store, Settings())
    run = store.get(run.id)
    store.review(
        run.id,
        ReviewInput(
            idempotency_key="review",
            reviewer="test",
            revision=run.revision,
            target_finding_revision=1,
            verdict="no_issue",
        ),
    )
    with store.engine.connect() as conn:
        case_ids = list(conn.execute(select(cases.c.id)).scalars())
    freeze(store, FreezeRequest(name="Private snapshot", case_ids=case_ids))
    with pytest.raises(Conflict):
        delete_run(store, run.id)
    delete_run(store, run.id, include_snapshots=True)
    with store.engine.connect() as conn:
        assert list(conn.execute(select(datasets.c.id)).scalars()) == []
