"""Local SQLite backup/restore and terminal-run deletion. Explicit paths only."""

import argparse
import sqlite3
from pathlib import Path
from sqlalchemy import delete
from ffv2.db import datasets, engine, runs
from ffv2.settings import Settings
from ffv2.store import Conflict, Store


def backup_sqlite(source: Path, destination: Path):
    if destination.exists() or source.resolve() == destination.resolve():
        raise ValueError("Backup destination must be new")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with (
        sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True) as src,
        sqlite3.connect(destination) as dst,
    ):
        src.backup(dst)
        if dst.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Backup integrity check failed")


def delete_run(store: Store, run_id: str, include_snapshots: bool = False):
    run = store.get(run_id)
    if run.status not in {"succeeded", "failed", "cancelled"}:
        raise Conflict("Cancel and wait for the worker before deletion")
    with store.engine.begin() as conn:
        # Frozen versions require explicit privacy invalidation, not silent label rewriting.
        from sqlalchemy import select

        snapshots = list(conn.execute(select(datasets)).mappings())
        matching = [
            snapshot
            for snapshot in snapshots
            if any(case.get("run_id") == run_id for case in snapshot["payload"].get("cases", []))
        ]
        if matching and not include_snapshots:
            raise Conflict("Dataset references this run; invalidate its private snapshot first")
        if include_snapshots:
            for snapshot in matching:
                conn.execute(delete(datasets).where(datasets.c.id == snapshot["id"]))
        if conn.scalar(select(runs.c.id).where(runs.c.parent_id == run_id)):
            raise Conflict("Delete child replays first")
        conn.execute(delete(runs).where(runs.c.id == run_id))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    backup = commands.add_parser("backup-sqlite")
    backup.add_argument("source", type=Path)
    backup.add_argument("destination", type=Path)
    remove = commands.add_parser("delete-run")
    remove.add_argument("run_id")
    remove.add_argument(
        "--include-snapshots",
        action="store_true",
        help="Explicit privacy deletion also removes frozen snapshots containing this run",
    )
    args = parser.parse_args()
    if args.command == "backup-sqlite":
        backup_sqlite(args.source, args.destination)
    else:
        delete_run(Store(engine(Settings().database_url)), args.run_id, args.include_snapshots)
