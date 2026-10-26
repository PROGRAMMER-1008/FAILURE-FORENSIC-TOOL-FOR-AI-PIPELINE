"""Explicit local .env launcher; services and tests do not implicitly load dotenv."""

import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

import httpx
from pydantic import SecretStr, ValidationError
from pydantic_settings import SettingsError

from ffv2.settings import Settings

ROOT = Path(__file__).resolve().parents[1]


def local_settings(path: Path) -> Settings:
    return Settings(_env_file=path, _env_file_encoding="utf-8")  # type: ignore[call-arg]


def child_environment(settings: Settings) -> dict[str, str]:
    env = dict(os.environ)
    for name, value in settings.model_dump().items():
        if isinstance(value, SecretStr):
            encoded = value.get_secret_value()
        elif isinstance(value, (list, dict)):
            encoded = json.dumps(value)
        else:
            encoded = str(value)
        env["FF_" + name.upper()] = encoded
    return env


def main(port: int = 8001):
    path = ROOT / ".env"
    if not path.exists():
        print("Missing .env. Copy .env.example to .env, then run again.")
        return 1
    try:
        settings = local_settings(path)
    except (ValidationError, ValueError, SettingsError, OSError):
        print(
            "Invalid local configuration. Check .env variable names and values. Values are hidden."
        )
        return 1
    if settings.mode != "local":
        print("This launcher requires FF_MODE=local. Use the deployment guide for hosted modes.")
        return 1
    if not (ROOT / "frontend/dist/index.html").exists():
        print("Build the frontend first: npm --prefix frontend run build")
        return 1
    with socket.socket() as probe:
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            print(f"Port {port} is occupied. Stop your previous local launcher, then try again.")
            return 1
    env = child_environment(settings)
    children: list[subprocess.Popen] = []
    try:
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=ROOT,
            env=env,
            check=True,
        )
        api = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "ffv2.api:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--no-access-log",
            ],
            cwd=ROOT,
            env=env,
        )
        children.append(api)
        ready = False
        with httpx.Client(trust_env=False, timeout=1) as client:
            for _ in range(40):
                if api.poll() is not None:
                    break
                try:
                    ready = client.get(f"http://127.0.0.1:{port}/health/ready").status_code == 200
                except httpx.HTTPError:
                    pass
                if ready:
                    break
                time.sleep(0.25)
        if not ready:
            print("Local API did not become ready; no worker started.")
            return 1
        if settings.ai_ready:
            children.append(
                subprocess.Popen(
                    [sys.executable, "-m", "ffv2.worker"],
                    cwd=ROOT,
                    env=env,
                )
            )
        else:
            print("Groq key missing. Setup UI is available; add FF_GROQ_API_KEY and restart.")
        print(f"Open http://127.0.0.1:{port}. Keep this terminal open; Ctrl+C stops the app.")
        if settings.provider == "groq":
            print(
                "Groq submissions send redacted documents to the cloud and use your account quota."
            )
        while all(child.poll() is None for child in children):
            time.sleep(0.5)
        print("A service stopped. Restart after checking the local configuration.")
        return 1
    except KeyboardInterrupt:
        return 0
    except (OSError, subprocess.CalledProcessError):
        print("Local startup failed. Check runtime installation and database access.")
        return 1
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
        for child in children:
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()


if __name__ == "__main__":
    raise SystemExit(main())
