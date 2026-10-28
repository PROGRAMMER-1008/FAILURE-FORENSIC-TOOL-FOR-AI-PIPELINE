from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import and_, delete, func, insert, or_, select, update
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import IntegrityError

from ffv2.db import (
    attempts,
    audit_events,
    cases,
    events,
    findings,
    jobs,
    judgments,
    pipeline_versions,
    reviews,
    runs,
)
from ffv2.visitors import visitor, run_scope
from ffv2.models import ReviewInput, Run, now, uid
from ffv2.privacy import fingerprint, redact


class Conflict(Exception):
    pass


class Missing(Exception):
    pass


class LostLease(Exception):
    pass


class Store:
    def __init__(self, engine: Engine):
        self.engine = engine

    def get(self, run_id: str) -> Run:
        with self.engine.connect() as conn:
            row = conn.execute(
                select(runs.c.payload).where(runs.c.id == run_id, run_scope())
            ).first()
        if row is None:
            raise Missing()
        return Run.model_validate(row[0])

    def list_runs(
        self,
        limit: int = 25,
        offset: int = 0,
        status: str | None = None,
        query_text: str = "",
        since: str | None = None,
        oldest_first: bool = False,
    ) -> list[dict]:
        query = (
            select(
                runs.c.id,
                runs.c.created_at,
                runs.c.updated_at,
                runs.c.status,
                runs.c.quality,
                runs.c.parent_id,
            )
            .order_by(
                runs.c.created_at.asc() if oldest_first else runs.c.created_at.desc(), runs.c.id
            )
            .limit(min(100, limit))
            .offset(offset)
        )
        query = query.where(run_scope())
        if status:
            query = query.where(runs.c.status == status)
        if query_text:
            query = query.where(
                or_(
                    runs.c.id.contains(query_text, autoescape=True),
                    runs.c.source_hash.contains(query_text, autoescape=True),
                )
            )
        if since:
            query = query.where(runs.c.created_at >= since)
        with self.engine.connect() as conn:
            return [dict(r) for r in conn.execute(query).mappings()]

    def stats(self) -> list[dict]:
        with self.engine.connect() as conn:
            return [
                dict(r)
                for r in conn.execute(
                    select(runs.c.status, runs.c.quality, func.count().label("count"))
                    .where(run_scope())
                    .group_by(runs.c.status, runs.c.quality)
                ).mappings()
            ]

    def _event(self, conn: Connection, run_id: str, kind: str, payload: dict) -> None:
        # Caller holds the run/job ownership lock. The PK enforces monotonic uniqueness.
        sequence = (
            conn.scalar(
                select(func.coalesce(func.max(events.c.sequence), 0)).where(
                    events.c.run_id == run_id
                )
            )
            or 0
        )
        sequence += 1
        conn.execute(
            insert(events).values(
                run_id=run_id,
                sequence=sequence,
                kind=kind,
                created_at=now(),
                payload=redact(payload),
            )
        )

    def enqueue(self, run: Run, key: str) -> Run:
        if identity := visitor.get():
            run.config["visitor_id"] = identity
            key = fingerprint([identity, key])
        request_hash = fingerprint(
            {"source": run.source, "config": run.config, "parent": run.parent_id}
        )
        try:
            with self.engine.begin() as conn:
                existing = conn.execute(select(jobs).where(jobs.c.key == key)).mappings().first()
                if existing:
                    if existing["request_hash"] != request_hash:
                        raise Conflict("Idempotency key already used for a different request")
                    return Run.model_validate(
                        conn.scalar(select(runs.c.payload).where(runs.c.id == existing["run_id"]))
                    )
                definition = run.pipeline.model_dump(mode="json")
                version = (
                    conn.execute(
                        select(pipeline_versions).where(pipeline_versions.c.id == run.pipeline.id)
                    )
                    .mappings()
                    .first()
                )
                if version and version["fingerprint"] != fingerprint(definition):
                    raise Conflict("Pipeline version is immutable")
                if not version:
                    conn.execute(
                        insert(pipeline_versions).values(
                            id=run.pipeline.id,
                            fingerprint=fingerprint(definition),
                            payload=definition,
                        )
                    )
                run = Run.model_validate(redact(run.model_dump(mode="json")))
                conn.execute(
                    insert(runs).values(
                        id=run.id,
                        created_at=run.created_at,
                        updated_at=run.updated_at,
                        status=run.status,
                        quality=run.quality,
                        revision=run.revision,
                        source_hash=run.source_hash,
                        parent_id=run.parent_id,
                        payload=run.model_dump(mode="json"),
                    )
                )
                conn.execute(
                    insert(jobs).values(
                        id=uid(),
                        run_id=run.id,
                        key=key,
                        request_hash=request_hash,
                        state="queued",
                        generation=0,
                        attempt_count=0,
                        cancel_requested=False,
                    )
                )
                self._event(conn, run.id, "queued", {})
            return run
        except IntegrityError:
            # Concurrent idempotent submissions: retry read after the winning commit.
            with self.engine.connect() as conn:
                existing = conn.execute(select(jobs).where(jobs.c.key == key)).mappings().first()
            if existing and existing["request_hash"] == request_hash:
                return self.get(existing["run_id"])
            raise Conflict("Concurrent submission conflict") from None

    def claim(self, owner: str, lease_seconds: int = 180, max_attempts: int = 3) -> dict | None:
        current = now()
        expires = (datetime.now(timezone.utc) + timedelta(seconds=lease_seconds)).isoformat()
        eligible = or_(
            jobs.c.state == "queued", and_(jobs.c.state == "running", jobs.c.lease_until < current)
        )
        with self.engine.begin() as conn:
            query = select(jobs).where(eligible).order_by(jobs.c.id).limit(1)
            if self.engine.dialect.name == "postgresql":
                query = query.with_for_update(skip_locked=True)
            row = conn.execute(query).mappings().first()
            if not row:
                return None
            if row["attempt_count"] >= max_attempts:
                conn.execute(update(jobs).where(jobs.c.id == row["id"]).values(state="failed"))
                run = Run.model_validate(
                    conn.scalar(select(runs.c.payload).where(runs.c.id == row["run_id"]))
                )
                run.status = "failed"
                self._save(conn, run)
                self._event(conn, run.id, "failed", {"reason": "Recovery attempt budget exhausted"})
                return None
            generation = row["generation"] + 1
            changed = conn.execute(
                update(jobs)
                .where(jobs.c.id == row["id"], jobs.c.generation == row["generation"], eligible)
                .values(
                    owner=owner,
                    generation=generation,
                    state="running",
                    lease_until=expires,
                    attempt_count=row["attempt_count"] + 1,
                )
            )
            if changed.rowcount != 1:
                return None
            return dict(row, owner=owner, generation=generation, lease_until=expires)

    def _ownership(self, conn: Connection, claim: dict) -> Any:
        row = (
            conn.execute(select(jobs).where(jobs.c.id == claim["id"]).with_for_update())
            .mappings()
            .first()
        )
        if (
            not row
            or row["owner"] != claim["owner"]
            or row["generation"] != claim["generation"]
            or row["state"] != "running"
            or row["lease_until"] < now()
        ):
            raise LostLease()
        return row

    def heartbeat(self, claim: dict, lease_seconds: int = 180) -> bool:
        with self.engine.begin() as conn:
            row = self._ownership(conn, claim)
            conn.execute(
                update(jobs)
                .where(jobs.c.id == claim["id"])
                .values(
                    lease_until=(
                        datetime.now(timezone.utc) + timedelta(seconds=lease_seconds)
                    ).isoformat()
                )
            )
            return bool(row["cancel_requested"])

    def _save(self, conn: Connection, run: Run) -> None:
        # created_at is immutable, including null legacy timestamps.
        old = conn.execute(
            select(runs.c.created_at, runs.c.revision).where(runs.c.id == run.id).with_for_update()
        ).first()
        if old is None:
            raise Missing()
        run.created_at = old[0]
        run.revision = old[1] + 1
        run.updated_at = now()
        payload = redact(run.model_dump(mode="json"))
        conn.execute(
            update(runs)
            .where(runs.c.id == run.id)
            .values(
                updated_at=run.updated_at,
                status=run.status,
                quality=run.quality,
                revision=run.revision,
                payload=payload,
            )
        )
        for attempt in run.attempts:
            data = redact(attempt.model_dump(mode="json"))
            exists = conn.scalar(select(attempts.c.id).where(attempts.c.id == attempt.id))
            if exists:
                conn.execute(
                    update(attempts).where(attempts.c.id == attempt.id).values(payload=data)
                )
            else:
                conn.execute(
                    insert(attempts).values(
                        id=attempt.id,
                        run_id=run.id,
                        step_id=attempt.step_id,
                        number=attempt.number,
                        payload=data,
                    )
                )
            if attempt.judgment and not conn.scalar(
                select(judgments.c.attempt_id).where(judgments.c.attempt_id == attempt.id)
            ):
                conn.execute(
                    insert(judgments).values(attempt_id=attempt.id, payload=data["judgment"])
                )
        if run.finding and not conn.scalar(
            select(findings.c.revision).where(
                findings.c.run_id == run.id, findings.c.revision == run.finding.revision
            )
        ):
            conn.execute(
                insert(findings).values(
                    run_id=run.id, revision=run.finding.revision, payload=payload["finding"]
                )
            )

    def checkpoint(
        self, run: Run, claim: dict, kind: str, payload: dict | None = None, terminal: bool = False
    ) -> None:
        with self.engine.begin() as conn:
            ownership = self._ownership(conn, claim)
            if terminal and ownership["cancel_requested"]:
                run.status = "cancelled"
                kind = "cancelled"
            self._save(conn, run)
            self._event(conn, run.id, kind, payload or {})
            if terminal:
                conn.execute(
                    update(jobs)
                    .where(jobs.c.id == claim["id"])
                    .values(state=run.status, lease_until=None)
                )

    def cancel(self, run_id: str) -> None:
        self.get(run_id)
        with self.engine.begin() as conn:
            row = (
                conn.execute(select(jobs).where(jobs.c.run_id == run_id).with_for_update())
                .mappings()
                .first()
            )
            if not row:
                raise Missing()
            if row["state"] in {"succeeded", "failed", "cancelled"}:
                return
            conn.execute(update(jobs).where(jobs.c.id == row["id"]).values(cancel_requested=True))
            if row["state"] == "queued":
                run = Run.model_validate(
                    conn.scalar(select(runs.c.payload).where(runs.c.id == run_id))
                )
                run.status = "cancelled"
                self._save(conn, run)
                conn.execute(update(jobs).where(jobs.c.id == row["id"]).values(state="cancelled"))
                self._event(conn, run_id, "cancelled", {})
            else:
                self._event(conn, run_id, "cancel_requested", {})

    def event_list(self, run_id: str, after: int = 0) -> list[dict]:
        self.get(run_id)
        with self.engine.connect() as conn:
            return [
                dict(r)
                for r in conn.execute(
                    select(events)
                    .where(events.c.run_id == run_id, events.c.sequence > after)
                    .order_by(events.c.sequence)
                    .limit(200)
                ).mappings()
            ]

    def review(self, run_id: str, request: ReviewInput) -> dict:
        self.get(run_id)
        with self.engine.begin() as conn:
            current = conn.execute(
                select(runs.c.payload).where(runs.c.id == run_id).with_for_update()
            ).first()
            if not current:
                raise Missing()
            run = Run.model_validate(current[0])
            prior = conn.execute(
                select(reviews.c.payload).where(
                    reviews.c.run_id == run_id, reviews.c.key == request.idempotency_key
                )
            ).first()
            payload = redact(request.model_dump(mode="json"))
            if prior:
                if prior[0]["request"] != payload:
                    raise Conflict("Review key conflict")
                return prior[0]
            if run.status not in {"succeeded", "failed", "cancelled"}:
                raise Conflict("Review requires a terminal run")
            if (
                request.revision != run.revision
                or not run.finding
                or request.target_finding_revision != run.finding.revision
            ):
                raise Conflict("Review target changed; reload the run")
            if not set(request.origins) <= {s.id for s in run.pipeline.steps}:
                raise Conflict("Unknown origin step")
            if request.verdict in {"confirm", "correct", "missed_failure"} and not request.origins:
                raise Conflict("Explicit origin labels required")
            if request.verdict == "no_issue" and request.origins:
                raise Conflict("No-issue review cannot name origins")
            previous = list(
                conn.execute(select(reviews.c.payload).where(reviews.c.run_id == run_id)).scalars()
            )
            labels = [
                p["request"]["origins"] for p in previous if p["request"]["verdict"] != "unclear"
            ]
            conflict = any(set(label) != set(request.origins) for label in labels)
            record = {
                "id": uid(),
                "request": payload,
                "label_state": "unresolved"
                if conflict or request.verdict == "unclear"
                else "reviewed",
                "created_at": now(),
            }
            conn.execute(
                insert(reviews).values(
                    id=record["id"],
                    run_id=run_id,
                    key=request.idempotency_key,
                    revision=run.revision + 1,
                    created_at=record["created_at"],
                    payload=record,
                )
            )
            if conflict:
                # Existing derived labels are no longer eligible; historical reviews stay intact.
                conn.execute(delete(cases).where(cases.c.run_id == run_id))
            elif record["label_state"] == "reviewed":
                conn.execute(
                    insert(cases).values(
                        id=uid(),
                        run_id=run_id,
                        review_id=record["id"],
                        family=run.source_hash,
                        split="feedback",
                        payload=record,
                    )
                )
            run.quality = (
                "inconclusive"
                if record["label_state"] == "unresolved"
                else ("acceptable" if request.verdict == "no_issue" else "confirmed_issue")
            )
            self._save(conn, run)
            conn.execute(
                insert(audit_events).values(
                    id=uid(),
                    created_at=now(),
                    action="review",
                    payload={"run_id": run_id, "review_id": record["id"]},
                )
            )
            return record
