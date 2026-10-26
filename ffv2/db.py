"""Canonical relational storage; JSON payload columns belong to the same transaction."""

from pathlib import Path
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    create_engine,
    event,
)
from sqlalchemy.engine import Engine

metadata = MetaData()
owner_sessions = Table(
    "owner_sessions",
    metadata,
    Column("id", String, primary_key=True),
    Column("expires", Integer, nullable=False, index=True),
    Column("revision", String, nullable=False),
)
usage_windows = Table(
    "usage_windows",
    metadata,
    Column("key", String, primary_key=True),
    Column("used", Integer, nullable=False),
    Column("expires", Integer, nullable=False, index=True),
)
pipeline_versions = Table(
    "pipeline_versions",
    metadata,
    Column("id", String, primary_key=True),
    Column("fingerprint", String, nullable=False),
    Column("payload", JSON, nullable=False),
)
runs = Table(
    "runs",
    metadata,
    Column("id", String, primary_key=True),
    Column("created_at", String),
    Column("updated_at", String, nullable=False),
    Column("status", String, nullable=False, index=True),
    Column("quality", String, nullable=False, index=True),
    Column("revision", Integer, nullable=False, default=0),
    Column("source_hash", String, index=True),
    Column("parent_id", String),
    Column("payload", JSON, nullable=False),
)
attempts = Table(
    "attempts",
    metadata,
    Column("id", String, primary_key=True),
    Column("run_id", String, ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("step_id", String, nullable=False),
    Column("number", Integer, nullable=False),
    Column("payload", JSON, nullable=False),
    UniqueConstraint("run_id", "step_id", "number"),
)
judgments = Table(
    "judgments",
    metadata,
    Column("attempt_id", String, ForeignKey("attempts.id", ondelete="CASCADE"), primary_key=True),
    Column("payload", JSON, nullable=False),
)
findings = Table(
    "findings",
    metadata,
    Column("run_id", String, ForeignKey("runs.id", ondelete="CASCADE"), primary_key=True),
    Column("revision", Integer, primary_key=True),
    Column("payload", JSON, nullable=False),
)
jobs = Table(
    "jobs",
    metadata,
    Column("id", String, primary_key=True),
    Column(
        "run_id", String, ForeignKey("runs.id", ondelete="CASCADE"), unique=True, nullable=False
    ),
    Column("key", String, unique=True, nullable=False),
    Column("request_hash", String, nullable=False),
    Column("state", String, nullable=False, index=True),
    Column("owner", String),
    Column("generation", Integer, nullable=False, default=0),
    Column("lease_until", String),
    Column("attempt_count", Integer, nullable=False, default=0),
    Column("cancel_requested", Boolean, nullable=False, default=False),
)
events = Table(
    "run_events",
    metadata,
    Column("run_id", String, ForeignKey("runs.id", ondelete="CASCADE"), primary_key=True),
    Column("sequence", Integer, primary_key=True),
    Column("kind", String, nullable=False),
    Column("created_at", String, nullable=False),
    Column("payload", JSON, nullable=False),
)
reviews = Table(
    "reviews",
    metadata,
    Column("id", String, primary_key=True),
    Column("run_id", String, ForeignKey("runs.id", ondelete="CASCADE"), nullable=False),
    Column("key", String, nullable=False),
    Column("revision", Integer, nullable=False),
    Column("created_at", String, nullable=False),
    Column("payload", JSON, nullable=False),
    UniqueConstraint("run_id", "key"),
    UniqueConstraint("run_id", "revision"),
)
cases = Table(
    "eval_cases",
    metadata,
    Column("id", String, primary_key=True),
    Column("run_id", String, ForeignKey("runs.id", ondelete="CASCADE")),
    Column("review_id", String, ForeignKey("reviews.id", ondelete="CASCADE"), unique=True),
    Column("family", String, nullable=False),
    Column("split", String, nullable=False),
    Column("payload", JSON, nullable=False),
)
datasets = Table(
    "dataset_versions",
    metadata,
    Column("id", String, primary_key=True),
    Column("created_at", String, nullable=False),
    Column("payload", JSON, nullable=False),
)
experiments = Table(
    "experiments",
    metadata,
    Column("id", String, primary_key=True),
    Column("created_at", String, nullable=False),
    Column("payload", JSON, nullable=False),
)
results = Table(
    "results",
    metadata,
    Column("id", String, primary_key=True),
    Column("experiment_id", String, ForeignKey("experiments.id", ondelete="CASCADE")),
    Column("payload", JSON, nullable=False),
)
audit_events = Table(
    "audit_events",
    metadata,
    Column("id", String, primary_key=True),
    Column("created_at", String, nullable=False),
    Column("action", String, nullable=False),
    Column("payload", JSON, nullable=False),
)
imports = Table(
    "legacy_imports",
    metadata,
    Column("legacy_id", String, primary_key=True),
    Column("run_id", String, ForeignKey("runs.id", ondelete="CASCADE")),
    Column("hash", String, nullable=False),
)


def engine(url: str) -> Engine:
    if url.startswith("sqlite:///") and ":memory:" not in url:
        Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    connection_options: dict[str, Any] = (
        {"check_same_thread": False} if url.startswith("sqlite") else {"connect_timeout": 5}
    )
    eng = create_engine(
        url,
        connect_args=connection_options,
        hide_parameters=True,
    )
    if url.startswith("sqlite"):

        @event.listens_for(eng, "connect")
        def pragmas(connection: Any, record: Any) -> None:
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA busy_timeout=5000")

    return eng
