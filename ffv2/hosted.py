"""Render entry point. Runtime-only secrets; no implicit dotenv reads."""

import argparse
import os
import signal
import subprocess
import sys
import time
from threading import Event

from sqlalchemy import text

from ffv2.db import engine
from ffv2.settings import Settings


def migrate(settings: Settings) -> int:
    """Serialize release migrations across overlapping free-service deployments."""
    eng = engine(settings.database_url)
    try:
        with eng.connect() as conn:
            postgres = eng.dialect.name == "postgresql"
            if postgres:
                conn.execute(text("SELECT pg_advisory_lock(1179012436)"))
            try:
                return subprocess.call([sys.executable, "-m", "alembic", "upgrade", "head"])
            finally:
                if postgres:
                    conn.execute(text("SELECT pg_advisory_unlock(1179012436)"))
    finally:
        eng.dispose()


def supervise(commands: list[list[str]]) -> int:
    stop = Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    children: list[subprocess.Popen] = []
    try:
        for command in commands:
            children.append(subprocess.Popen(command))
        while not stop.wait(0.5):
            if any(child.poll() is not None for child in children):
                return 1
        return 0
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
        for child in children:
            try:
                child.wait(timeout=15)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("role", choices=["web", "worker", "migrate", "project"])
    args = parser.parse_args()
    if not os.environ.get("FF_PUBLIC_ORIGIN") and os.environ.get("RENDER_EXTERNAL_HOSTNAME"):
        os.environ["FF_PUBLIC_ORIGIN"] = "https://" + os.environ["RENDER_EXTERNAL_HOSTNAME"]
    settings = Settings()
    if args.role in {"web", "project"} and settings.mode != "hosted":
        raise SystemExit("Hosted web requires protected hosted mode")
    # A Render connection string uses postgresql://; propagate the normalized driver to Alembic.
    os.environ["FF_DATABASE_URL"] = settings.database_url
    if args.role == "migrate":
        return migrate(settings)
    if args.role == "project" and migrate(settings) != 0:
        return 1
    if args.role == "worker":
        eng = engine(settings.database_url)
        try:
            for _ in range(120):
                try:
                    with eng.connect() as conn:
                        if (
                            conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
                            == "0003"
                        ):
                            break
                except Exception:
                    pass
                time.sleep(2)
            else:
                raise SystemExit("Database release migration not ready; worker did not start")
        finally:
            eng.dispose()
        command = [sys.executable, "-m", "ffv2.worker"]
    else:
        command = [
            sys.executable,
            "-m",
            "uvicorn",
            "ffv2.api:app",
            "--host",
            "0.0.0.0",
            "--port",
            os.environ.get("PORT", "8000"),
            "--no-proxy-headers",
            "--no-access-log",
        ]
    if args.role == "project":
        return supervise([command, [sys.executable, "-m", "ffv2.worker"]])
    if os.name != "nt":
        os.execv(sys.executable, command)
    child = subprocess.Popen(command)
    signal.signal(signal.SIGTERM, lambda *_: child.terminate())
    try:
        return child.wait()
    except KeyboardInterrupt:
        child.terminate()
        return child.wait()


if __name__ == "__main__":
    raise SystemExit(main())
