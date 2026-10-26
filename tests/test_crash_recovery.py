import multiprocessing
import time
import pytest
from sqlalchemy import update
from ffv2.db import engine, jobs
from ffv2.models import Run
from ffv2.settings import Settings
from ffv2.store import Store
from ffv2.worker import SYNTHETIC_SOURCE, run_one
from ffv2.providers import FakeProvider


def stalled_worker(url, started):
    class StalledProvider(FakeProvider):
        def generate(self, step, inputs):
            started.set()
            time.sleep(30)
            return super().generate(step, inputs)

    run_one(Store(engine(url)), Settings(), StalledProvider())


@pytest.mark.enable_socket
def test_killed_worker_keeps_running_attempt_and_recovers(store):
    run = store.enqueue(Run(source=SYNTHETIC_SOURCE, source_hash="crash-fixture"), "crash")
    context = multiprocessing.get_context("spawn")
    started = context.Event()
    process = context.Process(target=stalled_worker, args=(str(store.engine.url), started))
    process.start()
    try:
        assert started.wait(10), "worker never reached provider call"
        assert store.get(run.id).attempts[0].result.status == "running"
        process.terminate()
        process.join(timeout=5)
        with store.engine.begin() as conn:
            conn.execute(
                update(jobs).where(jobs.c.run_id == run.id).values(lease_until="2000-01-01")
            )
        assert run_one(Store(store.engine), Settings())
        restored = store.get(run.id)
        assert restored.status == "succeeded"
        assert restored.attempts[0].result.status == "failed"
        assert restored.attempts[1].number == 2
        assert restored.source == SYNTHETIC_SOURCE
    finally:
        if process.is_alive():
            process.terminate()
        process.join(timeout=5)
