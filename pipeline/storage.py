"""
Storage for traces.

WHY BOTH JSON FILES AND SQLITE:
- Each full trace is saved as a human-readable JSON file. You can open
  one in a text editor and read exactly what happened, step by step.
  This is your "camera footage archive."
- SQLite holds a lightweight INDEX (trace_id, doc_id, status, timestamp)
  so we can quickly query "show me all degraded traces" without having
  to open and parse every JSON file. This mirrors the guide's own design:
  "structured JSON files + SQLite index."
"""

import json
import sqlite3
import os
from datetime import datetime, timezone

from pipeline.models import Trace, EvalCase

DATA_DIR = "data"
TRACES_DIR = os.path.join(DATA_DIR, "traces")
DB_PATH = os.path.join(DATA_DIR, "forensics.db")


def _ensure_dirs():
    os.makedirs(TRACES_DIR, exist_ok=True)


def init_db():
    """Creates the SQLite index table if it doesn't exist yet. Safe to call every run."""
    _ensure_dirs()
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS traces (
            trace_id TEXT PRIMARY KEY,
            doc_id TEXT NOT NULL,
            status TEXT NOT NULL,
            flagged_bad INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            json_path TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS eval_cases (
            eval_case_id TEXT PRIMARY KEY,
            source_trace_id TEXT NOT NULL,
            doc_id TEXT NOT NULL,
            original_input_text TEXT NOT NULL,
            failing_step TEXT NOT NULL,
            bad_output TEXT NOT NULL,
            correct_output TEXT NOT NULL,
            failure_category TEXT NOT NULL,
            verdict TEXT NOT NULL,
            reviewer_notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def save_trace(trace: Trace) -> str:
    """
    Saves a trace to a JSON file and records it in the SQLite index.
    Returns the path to the saved JSON file.
    """
    _ensure_dirs()
    init_db()

    json_path = os.path.join(TRACES_DIR, f"{trace.trace_id}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        f.write(trace.model_dump_json(indent=2))

    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """INSERT OR REPLACE INTO traces (trace_id, doc_id, status, flagged_bad, created_at, json_path)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            trace.trace_id,
            trace.doc_id,
            trace.status.value,
            int(trace.flagged_bad),
            datetime.now(timezone.utc).isoformat(),
            json_path,
        ),
    )
    conn.commit()
    conn.close()

    return json_path


def load_trace(trace_id: str) -> Trace:
    """Loads a single trace back from its JSON file."""
    json_path = os.path.join(TRACES_DIR, f"{trace_id}.json")
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return Trace(**data)


def list_traces(status_filter: str | None = None) -> list[dict]:
    """
    Returns lightweight trace metadata from the SQLite index (fast -
    doesn't open every JSON file). Optionally filter by status
    ("success", "failure", "degraded").
    """
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    if status_filter:
        rows = conn.execute(
            "SELECT * FROM traces WHERE status = ? ORDER BY created_at DESC", (status_filter,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM traces ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(row) for row in rows]


def mark_trace_flagged(trace_id: str):
    """Sets flagged_bad=True on a trace, both in the JSON file and the SQLite index."""
    trace = load_trace(trace_id)
    trace.flagged_bad = True
    save_trace(trace)  # save_trace does INSERT OR REPLACE, so this updates both places


def save_eval_case(case: "EvalCase"):
    """Saves one human-reviewed eval case (the 'flashcard') to SQLite."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """INSERT OR REPLACE INTO eval_cases
           (eval_case_id, source_trace_id, doc_id, original_input_text, failing_step,
            bad_output, correct_output, failure_category, verdict, reviewer_notes, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            case.eval_case_id, case.source_trace_id, case.doc_id, case.original_input_text,
            case.failing_step, case.bad_output, case.correct_output, case.failure_category,
            case.verdict.value, case.reviewer_notes, case.created_at,
        ),
    )
    conn.commit()
    conn.close()


def load_eval_dataset(ground_truth_only: bool = True) -> list[dict]:
    """
    Returns the growing eval dataset. By default, only returns
    CONFIRMED or CORRECTED cases (real ground truth) - UNCLEAR cases
    are excluded unless ground_truth_only=False, since they shouldn't
    be treated as reliable labels for regression testing.
    """
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    if ground_truth_only:
        rows = conn.execute(
            "SELECT * FROM eval_cases WHERE verdict IN ('confirmed', 'corrected') ORDER BY created_at DESC"
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM eval_cases ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(row) for row in rows]
