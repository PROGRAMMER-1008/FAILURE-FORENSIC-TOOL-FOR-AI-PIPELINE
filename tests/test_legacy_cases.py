import json
import sqlite3
from ffv2.import_legacy import migrate
from ffv2.db import cases
from sqlalchemy import select


def test_legacy_eval_cases_preserve_provenance_without_invented_labels(store, tmp_path):
    source = tmp_path / "legacy"
    (source / "traces").mkdir(parents=True)
    (source / "traces" / "trace.json").write_text(
        json.dumps({"trace_id": "legacy-trace", "doc_id": "synthetic", "spans": []})
    )
    with sqlite3.connect(source / "forensics.db") as conn:
        conn.execute("CREATE TABLE traces(trace_id TEXT, created_at TEXT)")
        conn.execute("INSERT INTO traces VALUES('legacy-trace','2020-01-01T00:00:00+00:00')")
        conn.execute(
            "CREATE TABLE eval_cases(eval_case_id TEXT,source_trace_id TEXT,doc_id TEXT,original_input_text TEXT,failing_step TEXT,bad_output TEXT,correct_output TEXT,failure_category TEXT,verdict TEXT,reviewer_notes TEXT,created_at TEXT)"
        )
        conn.execute(
            "INSERT INTO eval_cases VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (
                "old-case",
                "legacy-trace",
                "synthetic",
                "Invented source",
                "extraction",
                "bad",
                "gold",
                "extraction",
                "confirmed",
                "historical note",
                "2020-01-02T00:00:00+00:00",
            ),
        )
    assert migrate(source, store)["eval_cases_imported"] == 1
    assert migrate(source, store, True, tmp_path / "backup")["eval_cases_imported"] == 1
    assert migrate(source, store)["eval_case_duplicates"] == 1
    with store.engine.connect() as conn:
        record = conn.scalar(select(cases.c.payload))
    assert record["label_state"] == "legacy_unverified"
    assert record["legacy"]["correct_output"] == "gold"
    assert record["created_at"] == "2020-01-02T00:00:00+00:00"
