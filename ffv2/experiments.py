"""Explicit fixture experiments and exact structured-output replay scoring."""

from typing import Literal
from sqlalchemy import insert, select
from ffv2.benchmark import benchmark
from ffv2.db import experiments, results, reviews
from ffv2.models import Model, Run, now
from ffv2.visitors import visitor
from ffv2.privacy import fingerprint
from ffv2.store import Missing, Store


class ExperimentRequest(Model):
    mode: Literal["synthetic"]
    dataset_version: Literal["curated-mechanics-1"] = "curated-mechanics-1"
    idempotency_key: str


def experiment(store: Store, request: ExperimentRequest) -> dict:
    experiment_id = fingerprint([visitor.get(), request.model_dump()])
    with store.engine.connect() as conn:
        existing = conn.scalar(
            select(experiments.c.payload).where(experiments.c.id == experiment_id)
        )
    if existing:
        return existing
    report = benchmark(None)
    rows = report.pop("results")
    record = {"id": experiment_id, "created_at": now(), "report": report}
    if identity := visitor.get():
        record["visitor_id"] = identity
    with store.engine.begin() as conn:
        conn.execute(
            insert(experiments).values(
                id=experiment_id, created_at=record["created_at"], payload=record
            )
        )
        for row in rows:
            conn.execute(
                insert(results).values(
                    id=fingerprint([experiment_id, row]), experiment_id=experiment_id, payload=row
                )
            )
    return record


def compare(store: Store, replay: Run) -> dict:
    if not replay.parent_id:
        raise Missing()
    original = store.get(replay.parent_id)

    def outputs(run):
        return {a.step_id: a.result.output for a in run.attempts if a.result.status == "succeeded"}

    before, after = outputs(original), outputs(replay)
    with store.engine.connect() as conn:
        history = list(
            conn.execute(
                select(reviews.c.payload)
                .where(reviews.c.run_id == original.id)
                .order_by(reviews.c.revision.desc())
            ).scalars()
        )
    expected = next(
        (
            r["request"]["expected_output"]
            for r in history
            if r["label_state"] == "reviewed" and r["request"].get("expected_output")
        ),
        None,
    )
    score = None
    # Scoring requires explicit step-keyed expected fields; no guessed gold values.
    if expected and all(
        step in {s.id for s in original.pipeline.steps} and isinstance(fields, dict) and fields
        for step, fields in expected.items()
    ):

        def match(actual):
            return all(
                actual.get(step) and all(actual[step].get(k) == v for k, v in fields.items())
                for step, fields in expected.items()
            )

        score = {
            "scorer_version": "explicit-fields-exact-1",
            "original_pass": bool(match(before)),
            "replay_pass": bool(match(after)),
            "expected": expected,
        }
    return {
        "original_id": original.id,
        "replay_id": replay.id,
        "intervention": replay.config.get("replay"),
        "before": before,
        "after": after,
        "changed_steps": [step for step in after if before.get(step) != after[step]],
        "score": score,
        "limitation": "No score without explicit step-keyed expected output; one intervention is not proof of causality",
    }
