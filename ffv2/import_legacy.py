"""Read-only dry-run by default. Never modify legacy files or infer missing timestamps."""

import argparse
import json
import shutil
import sqlite3
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import insert, select

from ffv2.db import engine, imports, cases
from ffv2.models import Attempt, Envelope, Run, PipelineVersion, Step, now
from ffv2.privacy import fingerprint, redact
from ffv2.settings import Settings
from ffv2.store import Store
from pipeline.models import Trace, EvalCase


def migrate(directory: Path, store: Store, apply: bool = False, backup: Path | None = None) -> dict:
    report: dict = {
        "mode": "apply" if apply else "dry-run",
        "imported": 0,
        "duplicates": 0,
        "orphans": [],
        "corrupt": [],
        "changed": [],
        "missing_files": [],
        "eval_cases_imported": 0,
        "eval_case_duplicates": 0,
        "invalid_eval_cases": [],
        "orphan_eval_cases": [],
    }
    trace_dir = directory / "traces"
    index: dict = {}
    database = directory / "forensics.db"
    legacy_cases = []
    if database.exists():
        with sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True) as conn:
            index = {r[0]: r[1] for r in conn.execute("SELECT trace_id, created_at FROM traces")}
            if conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='eval_cases'"
            ).fetchone():
                conn.row_factory = sqlite3.Row
                legacy_cases = [dict(row) for row in conn.execute("SELECT * FROM eval_cases")]
    if apply:
        if (
            backup is None
            or backup.exists()
            or backup.resolve().is_relative_to(directory.resolve())
        ):
            raise ValueError(
                "Apply requires a new backup directory outside the legacy data directory"
            )
        backup.mkdir(parents=True)
        if database.exists():
            with (
                sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True) as src,
                sqlite3.connect(backup / "forensics.db") as dst,
            ):
                src.backup(dst)
        if trace_dir.exists():
            shutil.copytree(trace_dir, backup / "traces")
    found = set()
    for path in sorted(trace_dir.glob("*.json")):
        try:
            legacy = Trace.model_validate_json(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            report["corrupt"].append(path.name)
            continue
        found.add(legacy.trace_id)
        digest = fingerprint(legacy.model_dump(mode="json"))
        with store.engine.connect() as conn:
            prior = (
                conn.execute(select(imports).where(imports.c.legacy_id == legacy.trace_id))
                .mappings()
                .first()
            )
        if prior:
            if prior["hash"] != digest:
                report["changed"].append(path.name)
            if prior["hash"] == digest:
                report["duplicates"] += 1
            continue
        if legacy.trace_id not in index:
            report["orphans"].append(path.name)
        if not apply:
            report["imported"] += 1
            continue
        source = legacy.final_output.raw_document.raw_text if legacy.final_output else ""
        run = Run(
            id=str(uuid5(NAMESPACE_URL, "failure-forensics:legacy:" + legacy.trace_id)),
            source=redact(source),
            source_hash=fingerprint(source),
            created_at=index.get(legacy.trace_id),
            status="succeeded" if legacy.status.value != "failure" else "failed",
            quality="unassessed",
            pipeline=PipelineVersion(
                id="legacy-" + digest[:16],
                steps=[
                    Step(
                        id=f"legacy-{i}",
                        name=span.step_name,
                        dependencies=[],
                        contract="legacy-unverified",
                        prompt_version="unknown",
                    )
                    for i, span in enumerate(legacy.spans)
                ],
            ),
            config={
                "legacy_id": legacy.trace_id,
                "limitations": "Legacy success and raw responses are not reliable; timestamps may be unknown",
            },
        )
        for i, span in enumerate(legacy.spans):
            step_id = f"legacy-{i}"
            run.attempts.append(
                Attempt(
                    step_id=step_id,
                    dependencies=[],
                    started_at="unknown",
                    inputs={"legacy_input": redact(span.input_summary)},
                    result=Envelope(
                        status="succeeded" if span.success else "failed",
                        output={"legacy_output": redact(span.output_summary)},
                        raw_response="",
                        provider="legacy",
                        model="unknown",
                    ),
                )
            )
        # Store enqueue+terminal import+mapping in one outer transaction.
        with store.engine.begin() as conn:
            # Inline initial relational write avoids creating an executable legacy job.
            from ffv2.db import runs

            conn.execute(
                insert(runs).values(
                    id=run.id,
                    created_at=run.created_at,
                    updated_at=now(),
                    status=run.status,
                    quality=run.quality,
                    revision=0,
                    source_hash=run.source_hash,
                    payload=redact(run.model_dump(mode="json")),
                )
            )
            store._save(conn, run)
            conn.execute(
                insert(imports).values(legacy_id=legacy.trace_id, run_id=run.id, hash=digest)
            )
        report["imported"] += 1
    report["missing_files"] = sorted(set(index) - found)
    for record in legacy_cases:
        identifier = str(record.get("eval_case_id", "unknown"))
        try:
            case = EvalCase.model_validate(record)
        except ValueError:
            report["invalid_eval_cases"].append(identifier)
            continue
        stable_id = str(uuid5(NAMESPACE_URL, "failure-forensics:legacy-case:" + case.eval_case_id))
        digest = fingerprint(case.model_dump(mode="json"))
        with store.engine.connect() as conn:
            previous = conn.scalar(select(cases.c.payload).where(cases.c.id == stable_id))
            run_id = conn.scalar(
                select(imports.c.run_id).where(imports.c.legacy_id == case.source_trace_id)
            )
        if previous:
            if previous.get("legacy_hash") == digest:
                report["eval_case_duplicates"] += 1
            else:
                report["changed"].append("eval_case:" + identifier)
            continue
        if not run_id and case.source_trace_id not in found:
            report["orphan_eval_cases"].append(identifier)
            continue
        if apply:
            if not run_id:
                report["orphan_eval_cases"].append(identifier)
                continue
            with store.engine.begin() as conn:
                conn.execute(
                    insert(cases).values(
                        id=stable_id,
                        run_id=run_id,
                        review_id=None,
                        family=fingerprint(case.original_input_text),
                        split="legacy_unverified",
                        payload=redact(
                            {
                                "label_state": "legacy_unverified",
                                "legacy_hash": digest,
                                "legacy": case.model_dump(mode="json"),
                                "created_at": case.created_at or None,
                                "limitation": "Historical verdict preserved; reviewer identity and v2 target revision unknown. Re-review before scoring.",
                            }
                        ),
                    )
                )
        report["eval_cases_imported"] += 1
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup", type=Path)
    args = parser.parse_args()
    print(
        json.dumps(
            migrate(
                args.directory, Store(engine(Settings().database_url)), args.apply, args.backup
            ),
            indent=2,
        )
    )
