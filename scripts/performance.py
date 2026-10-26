"""Disposable 10k-summary infrastructure measurement; no inference capacity claim."""

import argparse
import asyncio
import json
import os
import platform
import statistics
import time
import tracemalloc
from threading import Thread
from pathlib import Path

import httpx
from sqlalchemy import insert
from ffv2.api import create_app
from ffv2.db import engine, metadata, runs
from ffv2.models import Run
from ffv2.settings import Settings
from ffv2.store import Store
from ffv2.worker import run_one
from ffv2.providers import FakeProvider


async def measure(store):
    app = create_app(Settings(), store)
    durations = []
    errors = 0
    active_job_requests = 0

    class SlowFake(FakeProvider):
        def generate(self, step, inputs):
            time.sleep(0.25)
            return super().generate(step, inputs)

    store.enqueue(
        Run(source="Synthetic concurrent job", source_hash="performance-job"),
        "performance-active-job",
    )
    worker = Thread(target=run_one, args=(store, Settings(), SlowFake()))
    worker.start()
    semaphore = asyncio.Semaphore(4)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:

        async def one(i):
            nonlocal errors, active_job_requests
            async with semaphore:
                start = time.perf_counter()
                active_job_requests += int(worker.is_alive())
                response = await client.get(
                    f"/api/v1/runs?limit=25&offset={(i % 100) * 25}&status=succeeded"
                )
                durations.append((time.perf_counter() - start) * 1000)
                if response.status_code != 200 or len(response.json()["items"]) != 25:
                    errors += 1

        await asyncio.gather(*(one(i) for i in range(200)))
    worker.join(timeout=10)
    if worker.is_alive():
        raise RuntimeError("Synthetic worker did not finish within measurement deadline")
    return durations, errors, active_job_requests


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("docs/performance.json"))
    args = parser.parse_args()
    if args.database.exists():
        raise ValueError("Use a new disposable database path")
    eng = engine(f"sqlite:///{args.database}")
    metadata.create_all(eng)
    with eng.begin() as conn:
        for chunk in range(20):
            rows = []
            for i in range(500):
                run = Run(
                    source="SYNTHETIC " + "x" * 1000,
                    source_hash=f"family-{chunk}-{i}",
                    status="succeeded",
                )
                rows.append(
                    {
                        "id": run.id,
                        "created_at": run.created_at,
                        "updated_at": run.updated_at,
                        "status": run.status,
                        "quality": run.quality,
                        "revision": 0,
                        "source_hash": run.source_hash,
                        "payload": run.model_dump(mode="json"),
                    }
                )
            conn.execute(insert(runs), rows)
    tracemalloc.start()
    start = time.perf_counter()
    durations, errors, active_job_requests = asyncio.run(measure(Store(eng)))
    elapsed = time.perf_counter() - start
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    durations.sort()
    report = {
        "mode": "in-process ASGI fake-infrastructure",
        "seeded_summaries": 10000,
        "source_characters_per_run": 1010,
        "requests": 200,
        "concurrency": 4,
        "elapsed_seconds": elapsed,
        "errors": errors,
        "requests_started_during_job": active_job_requests,
        "concurrent_job": "fake provider with 250ms injected per-call latency",
        "p50_ms": statistics.median(durations),
        "p95_ms": durations[189],
        "p99_ms": durations[197],
        "peak_python_tracked_bytes": peak,
        "platform": platform.platform(),
        "processor": platform.processor(),
        "logical_cpus": os.cpu_count(),
        "database": "SQLite",
        "limitations": [
            "In-process HTTP transport; not network/TLS production load",
            "Concurrent synthetic worker only; no real inference load",
            "Python allocation peak excludes native memory and OS cache",
            "No throughput SLA inferred; no timing CI threshold",
        ],
    }
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    eng.dispose()


if __name__ == "__main__":
    main()
