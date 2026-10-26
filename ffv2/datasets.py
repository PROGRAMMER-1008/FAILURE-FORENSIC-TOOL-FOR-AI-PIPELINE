"""Immutable feedback snapshots. Production feedback never enters the frozen fixture split."""

from sqlalchemy import insert, select
from ffv2.db import cases, datasets
from ffv2.models import Model, now
from ffv2.privacy import fingerprint, redact
from ffv2.store import Conflict, Missing, Store


class FreezeRequest(Model):
    name: str
    case_ids: list[str]


def freeze(store: Store, request: FreezeRequest) -> dict:
    if (
        not request.case_ids
        or len(request.case_ids) > 1000
        or len(set(request.case_ids)) != len(request.case_ids)
    ):
        raise Conflict("Select 1–1000 unique case IDs")
    with store.engine.begin() as conn:
        selected = [
            dict(row)
            for row in conn.execute(
                select(cases).where(cases.c.id.in_(request.case_ids)).order_by(cases.c.id)
            ).mappings()
        ]
        if len(selected) != len(request.case_ids):
            raise Missing()
        if any(row["payload"].get("label_state") != "reviewed" for row in selected):
            raise Conflict("Only reviewed, resolved labels can be frozen for evaluation")
        snapshot = redact(
            {
                "name": request.name,
                "split": "feedback",
                "cases": selected,
                "scorer_version": "origin-set-1",
                "execution_mode": "human_feedback_not_benchmark",
            }
        )
        digest = fingerprint(snapshot)
        existing = conn.scalar(select(datasets.c.payload).where(datasets.c.id == digest))
        if existing:
            return existing
        result = {"id": digest, "created_at": now(), **snapshot}
        conn.execute(
            insert(datasets).values(id=digest, created_at=result["created_at"], payload=result)
        )
        return result
