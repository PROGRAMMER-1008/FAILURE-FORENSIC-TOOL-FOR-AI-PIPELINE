import pytest
from ffv2.datasets import FreezeRequest, freeze
from ffv2.models import ReviewInput, Run
from ffv2.store import Conflict
from ffv2.worker import SYNTHETIC_SOURCE, run_one
from ffv2.db import cases
from sqlalchemy import select


def test_review_idempotency_conflict_and_frozen_snapshot(store):
    run = store.enqueue(
        Run(source=SYNTHETIC_SOURCE, source_hash="fixture", config={"injected": True}), "run"
    )
    run_one(store, __import__("ffv2.settings", fromlist=["Settings"]).Settings())
    run = store.get(run.id)
    review = ReviewInput(
        idempotency_key="a",
        reviewer="First reviewer",
        revision=run.revision,
        target_finding_revision=1,
        verdict="correct",
        origins=["extract"],
    )
    original = store.review(run.id, review)
    assert store.review(run.id, review) == original
    with store.engine.connect() as conn:
        ids = list(conn.execute(select(cases.c.id)).scalars())
    snapshot = freeze(store, FreezeRequest(name="Feedback v1", case_ids=ids))
    assert freeze(store, FreezeRequest(name="Feedback v1", case_ids=ids)) == snapshot
    changed = review.model_copy(
        update={
            "idempotency_key": "b",
            "revision": store.get(run.id).revision,
            "reviewer": "Independent reviewer",
            "origins": ["classify"],
        }
    )
    assert store.review(run.id, changed)["label_state"] == "unresolved"
    with store.engine.connect() as conn:
        assert list(conn.execute(select(cases.c.id)).scalars()) == []
    # The already-frozen snapshot is historical, not silently relabeled.
    assert snapshot["cases"][0]["payload"]["request"]["origins"] == ["extract"]
    with pytest.raises(Conflict):
        store.review(run.id, review.model_copy(update={"notes": "changed"}))
