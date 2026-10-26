"""Seed only invented content; use a dedicated demo DB with migrations applied."""

from ffv2.db import engine
from ffv2.models import Run
from ffv2.privacy import fingerprint
from ffv2.settings import Settings
from ffv2.store import Store
from ffv2.worker import SYNTHETIC_SOURCE, run_one


if __name__ == "__main__":
    settings = Settings(provider="fake")
    store = Store(engine(settings.database_url))
    for injected in (False, True):
        store.enqueue(
            Run(
                source=SYNTHETIC_SOURCE,
                source_hash=fingerprint(SYNTHETIC_SOURCE),
                config={
                    "provider": "fake",
                    "injected": injected,
                    "execution_mode": "recorded-synthetic-demo",
                },
            ),
            f"recorded-demo-v1-{injected}",
        )
    while run_one(store, settings):
        pass
    print("Synthetic demo seeded. Stop worker and serve this dedicated DB with FF_MODE=demo.")
