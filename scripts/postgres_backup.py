"""Private local Docker PostgreSQL backup/restore. Never prints credentials or dump content."""

import argparse
import subprocess
from pathlib import Path


def checked(command, **kwargs):
    result = subprocess.run(command, stderr=subprocess.PIPE, **kwargs)
    if result.returncode:
        raise RuntimeError(
            "PostgreSQL operation failed; check container availability/permissions without sharing secrets"
        )
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=["backup", "restore-new"])
    parser.add_argument("--container", required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument("--user", default="postgres")
    parser.add_argument("--file", type=Path, required=True)
    args = parser.parse_args()
    base = ["docker", "exec", args.container]
    if args.operation == "backup":
        args.file.parent.mkdir(parents=True, exist_ok=True)
        with args.file.open("xb") as output:
            checked(base + ["pg_dump", "-U", args.user, "-d", args.database, "-Fc"], stdout=output)
        print("Backup written; restore validation is required before relying on it.")
    else:
        # createdb fails if target exists. Never clean/drop or restore over existing data.
        checked(base + ["createdb", "-U", args.user, args.database], stdout=subprocess.DEVNULL)
        with args.file.open("rb") as source:
            checked(
                [
                    "docker",
                    "exec",
                    "-i",
                    args.container,
                    "pg_restore",
                    "--exit-on-error",
                    "--no-owner",
                    "-U",
                    args.user,
                    "-d",
                    args.database,
                ],
                stdin=source,
                stdout=subprocess.DEVNULL,
            )
        checked(
            base
            + [
                "psql",
                "-U",
                args.user,
                "-d",
                args.database,
                "-v",
                "ON_ERROR_STOP=1",
                "-c",
                "SELECT count(*) AS restored_run_count FROM runs;",
            ],
            stdout=subprocess.DEVNULL,
        )
        print(
            "Restored into a new database; runs table query succeeded. Compare source counts and run application smoke tests."
        )


if __name__ == "__main__":
    main()
