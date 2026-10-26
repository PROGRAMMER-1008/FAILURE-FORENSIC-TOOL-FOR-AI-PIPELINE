"""One in-flight call per worker. At-least-once calls, fenced database writes."""

import signal
import time
from threading import Event

from ffv2.db import engine
from ffv2.diagnosis import analyze, assess
from ffv2.models import Attempt, Citation, Envelope, Issue, Judgment, now, uid
from ffv2.providers import FakeProvider, Provider, configured_provider, execute
from ffv2.settings import Settings
from ffv2.limits import BudgetedProvider
from ffv2.store import LostLease, Store
from ffv2.tracer import Tracer


def synthetic_judgment(step: str, injected: bool) -> Judgment:
    issue = injected and step in {"extract", "summarize"}
    return Judgment(
        model="injected-fixture-1",
        assessment="issue" if issue else "acceptable",
        source_correct=not issue,
        input_faithful=step != "extract" or not issue,
        issues=[
            Issue(
                category="propagation" if step == "summarize" else "extraction",
                severity="high",
                field="entities[0].value" if step == "extract" else "summary",
                rationale="Injected 999 EUR conflicts with synthetic source total 814 EUR",
                citations=[Citation(start=0, end=14, quote="Total: 814 EUR")],
                inherited_from=["extract"] if step == "summarize" else [],
            )
        ]
        if issue
        else [],
        uncertainty="Known injected synthetic case; not model or human evaluation",
    )


SYNTHETIC_SOURCE = (
    "Total: 814 EUR\nSYNTHETIC INVOICE SYN-0001. Example Comet Workshop. Payment status: unknown."
)


def run_one(store: Store, settings: Settings, provider: Provider | None = None) -> bool:
    claim = store.claim(uid(), settings.lease_seconds, settings.max_job_attempts)
    if claim is None:
        return False
    run = store.get(claim["run_id"])
    settings = Settings.model_validate(
        {
            **settings.model_dump(),
            **{
                key: run.config[key]
                for key in ("provider", "producer_model", "judge_model")
                if key in run.config
            },
        }
    )
    provider = provider or configured_provider(settings)
    if isinstance(provider, FakeProvider) and run.config.get("injected"):
        provider.overrides["extract"] = (
            '{"entities":[{"name":"Total","value":"999 EUR","entity_type":"amount"}],"confidence":5}'
        )
    judge = configured_provider(settings, judge=True) if settings.provider != "fake" else None
    if settings.provider == "groq":
        provider = BudgetedProvider(provider, store.engine, settings.groq_daily_calls)
        if judge:
            judge = BudgetedProvider(judge, store.engine, settings.groq_daily_calls)
    run.status = "running"
    # Mark unfinished calls as interrupted before restarting. Never erase old attempts.
    for a in run.attempts:
        if a.result.status == "running":
            a.result.status = "failed"
            a.result.error = "provider_error"
            a.ended_at = now()
    store.checkpoint(run, claim, "running")
    tracer = Tracer(store, run, claim)
    outputs = {a.step_id: a.result.output for a in run.attempts if a.result.status == "succeeded"}
    for step in run.pipeline.steps:
        if store.heartbeat(claim, settings.lease_seconds):
            run.status = "cancelled"
            break
        if step.id in outputs:
            continue
        inputs = {
            "document": run.source,
            **{dep: outputs[dep] for dep in step.dependencies if dep in outputs},
        }
        if any(dep != "document" and dep not in outputs for dep in step.dependencies):
            run.attempts.append(
                Attempt(
                    step_id=step.id,
                    dependencies=step.dependencies,
                    inputs=inputs,
                    number=1
                    + max((a.number for a in run.attempts if a.step_id == step.id), default=0),
                    result=Envelope(status="skipped", provider=provider.name, model=provider.model),
                    ended_at=now(),
                )
            )
            store.checkpoint(run, claim, "step_skipped", {"step_id": step.id})
            continue
        for retry in range(2):
            with tracer.step(step, inputs, provider.name, provider.model) as attempt:
                attempt.result = execute(provider, step.id, inputs, settings.max_characters)
                store.heartbeat(claim, settings.lease_seconds)
                if attempt.result.status == "succeeded":
                    outputs[step.id] = attempt.result.output
                    if judge:
                        attempt.judgment = assess(
                            judge,
                            run.source,
                            inputs,
                            attempt.result.output or {},
                            settings.max_characters,
                        )
                    elif run.source == SYNTHETIC_SOURCE:
                        attempt.judgment = synthetic_judgment(
                            step.id, bool(run.config.get("injected"))
                        )
                    else:
                        attempt.judgment = Judgment(
                            model="fake",
                            status="unavailable",
                            assessment="inconclusive",
                            uncertainty="Fake provider does not evaluate arbitrary source content",
                        )
            if attempt.result.error not in {"timeout", "connection"} or retry == 1:
                break
            if store.heartbeat(claim, settings.lease_seconds):
                break
            time.sleep(0.1 * (2**retry))
    if run.status != "cancelled":
        run.status = (
            "cancelled"
            if store.heartbeat(claim, settings.lease_seconds)
            else ("succeeded" if len(outputs) == len(run.pipeline.steps) else "failed")
        )
    run.finding = analyze(run)
    run.quality = (
        "suspected_issue"
        if run.finding.origins
        else ("inconclusive" if run.finding.abstention_reason else "acceptable")
    )
    store.checkpoint(run, claim, run.status, terminal=True)
    return True


def main():
    settings = Settings()
    store = Store(engine(settings.database_url))
    stop = Event()
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    while not stop.is_set():
        try:
            if not run_one(store, settings):
                stop.wait(1)
        except LostLease:
            pass  # Another owner recovered the job. Do not overwrite it.


if __name__ == "__main__":
    main()
