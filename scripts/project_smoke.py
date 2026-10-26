"""Container-only synthetic smoke for the free web+worker supervisor."""

import time
from ffv2.db import engine
from ffv2.models import Run, uid
from ffv2.settings import Settings
from ffv2.store import Store
from ffv2.worker import SYNTHETIC_SOURCE


def main():
    settings = Settings()
    if settings.provider != "fake":
        raise SystemExit("Smoke test requires the synthetic provider")
    store = Store(engine(settings.database_url))
    run = store.enqueue(
        Run(source=SYNTHETIC_SOURCE, source_hash="fixture"), "project-smoke-" + uid()
    )
    for _ in range(60):
        current = store.get(run.id)
        if current.status == "succeeded":
            assert len(current.attempts) == 3
            print("Combined API/worker smoke passed")
            return
        if current.status in {"failed", "cancelled"}:
            raise SystemExit("Combined workflow failed")
        time.sleep(0.5)
    raise SystemExit("Combined worker did not finish within the deadline")


if __name__ == "__main__":
    main()
