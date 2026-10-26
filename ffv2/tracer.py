"""Small integration surface: caller executes work, tracer persists every boundary."""

from contextlib import contextmanager
from collections.abc import Iterator

from ffv2.models import Attempt, Envelope, Run, Step, now
from ffv2.store import Store


class Tracer:
    def __init__(self, store: Store, run: Run, claim: dict):
        self.store, self.run, self.claim = store, run, claim

    @contextmanager
    def step(self, step: Step, inputs: dict, provider: str, model: str) -> Iterator[Attempt]:
        attempt = Attempt(
            step_id=step.id,
            dependencies=step.dependencies,
            inputs=inputs,
            number=1
            + max((a.number for a in self.run.attempts if a.step_id == step.id), default=0),
            result=Envelope(status="running", provider=provider, model=model),
        )
        self.run.attempts.append(attempt)
        self.store.checkpoint(
            self.run, self.claim, "step_started", {"step_id": step.id, "attempt_id": attempt.id}
        )
        try:
            yield attempt
        except Exception:
            attempt.result.status = "failed"
            attempt.result.error = "provider_error"
            raise
        finally:
            attempt.ended_at = now()
            self.store.checkpoint(
                self.run,
                self.claim,
                "step_finished",
                {"step_id": step.id, "status": attempt.result.status},
            )
