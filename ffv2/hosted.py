"""Render entry point. Runtime-only secrets; no implicit dotenv reads."""

import argparse
import os
import signal
import subprocess
import sys
import time

from sqlalchemy import text

from ffv2.db import engine
from ffv2.settings import Settings


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("role", choices=["web", "worker", "migrate"])
    args = parser.parse_args()
    if not os.environ.get("FF_PUBLIC_ORIGIN") and os.environ.get("RENDER_EXTERNAL_HOSTNAME"):
        os.environ["FF_PUBLIC_ORIGIN"] = "https://" + os.environ["RENDER_EXTERNAL_HOSTNAME"]
    settings = Settings()
    if args.role == "web" and settings.mode != "hosted":
        raise SystemExit("Hosted web requires protected hosted mode")
    # A Render connection string uses postgresql://; propagate the normalized driver to Alembic.
    os.environ["FF_DATABASE_URL"] = settings.database_url
    if args.role == "migrate":
        return subprocess.call([sys.executable, "-m", "alembic", "upgrade", "head"])
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
