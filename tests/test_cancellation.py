from ffv2.models import Run


def test_cancellation_between_final_heartbeat_and_commit(store):
    run = store.enqueue(Run(source="synthetic cancellation", source_hash="fixture"), "race")
    claim = store.claim("worker")
    assert not store.heartbeat(claim)
    store.cancel(run.id)
    run.status = "succeeded"
    store.checkpoint(run, claim, "succeeded", terminal=True)
    assert store.get(run.id).status == "cancelled"
    assert store.event_list(run.id)[-1]["kind"] == "cancelled"
