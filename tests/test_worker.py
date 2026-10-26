from ffv2.models import Run
from ffv2.providers import FakeProvider
from ffv2.settings import Settings
from ffv2.worker import SYNTHETIC_SOURCE, run_one


def test_worker_partial_run_independent_branch_and_events(store):
    run = store.enqueue(Run(source=SYNTHETIC_SOURCE, source_hash="fixture"), "a")
    run_one(store, Settings(), FakeProvider({"extract": "broken"}))
    result = store.get(run.id)
    assert result.status == "failed"
    assert [a.result.status for a in result.attempts] == ["failed", "succeeded", "skipped"]
    assert result.finding.origins == ["extract"]
    assert store.event_list(run.id)[-1]["kind"] == "failed"


def test_worker_injected_origin_and_cancel(store):
    run = store.enqueue(
        Run(source=SYNTHETIC_SOURCE, source_hash="fixture", config={"injected": True}), "a"
    )
    run_one(store, Settings())
    result = store.get(run.id)
    assert result.finding.origins == ["extract"]
    assert result.finding.symptoms == ["summarize"]
    cancelled = store.enqueue(Run(source="other", source_hash="other"), "b")
    store.cancel(cancelled.id)
    assert store.get(cancelled.id).status == "cancelled"
    assert not run_one(store, Settings())
