"""Interactive local launcher. Never reads .env or writes the API key to disk."""

import getpass
import os
from pathlib import Path
import subprocess
import sys
import time
import warnings


def main():
    if not sys.stdin.isatty():
        raise SystemExit("Run this launcher in an interactive terminal for hidden key entry.")
    root = Path(__file__).resolve().parents[1]
    model = input("Groq model [openai/gpt-oss-20b]: ").strip() or "openai/gpt-oss-20b"
    with warnings.catch_warnings():
        warnings.simplefilter("error", getpass.GetPassWarning)
        key = getpass.getpass("Groq API key (hidden, not saved): ").strip()
    if not key:
        raise SystemExit("No key entered; nothing started.")
    env = dict(
        os.environ,
        FF_PROVIDER="groq",
        FF_MODE="local",
        FF_GROQ_API_KEY=key,
        FF_PRODUCER_MODEL=model,
        FF_JUDGE_MODEL=model,
        FF_DATABASE_URL="sqlite:///data/groq-preview.db",
    )
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"], cwd=root, env=env, check=True
    )
    children = []
    try:
        children.append(
            subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "ffv2.api:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "8001",
                    "--no-access-log",
                ],
                cwd=root,
                env=env,
            )
        )
        time.sleep(1)
        if children[0].poll() is not None:
            raise SystemExit("API did not start; check whether port 8001 is already occupied.")
        children.append(subprocess.Popen([sys.executable, "-m", "ffv2.worker"], cwd=root, env=env))
        print("Open http://127.0.0.1:8001. Submissions send data to Groq and use your quota.")
        print("Producer and judge use the same model; their errors may be correlated.")
        print("Keep this terminal open. Press Ctrl+C to stop both services.")
        while all(child.poll() is None for child in children):
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
        for child in children:
            child.wait()


if __name__ == "__main__":
    main()
