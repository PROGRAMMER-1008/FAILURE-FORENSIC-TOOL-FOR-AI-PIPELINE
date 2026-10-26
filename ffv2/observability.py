"""Operational telemetry only: no document, prompt, output or exception content."""

import json
import logging
import time
from contextlib import contextmanager
from threading import Lock

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.resources import Resource

logger = logging.getLogger("ffv2.operations")
_lock = Lock()
_counts: dict[str, int] = {}
_duration: dict[str, float] = {}
if isinstance(trace.get_tracer_provider(), trace.ProxyTracerProvider):
    trace.set_tracer_provider(
        TracerProvider(resource=Resource.create({"service.name": "failure-forensics"}))
    )
tracer = trace.get_tracer("failure-forensics-operations", "2.0")


@contextmanager
def operation(name: str):
    start = time.monotonic()
    outcome = "success"
    with tracer.start_as_current_span(name, record_exception=False, set_status_on_exception=False):
        try:
            yield
        except Exception:
            outcome = "error"
            raise
        finally:
            elapsed = time.monotonic() - start
            with _lock:
                key = f"{name}.{outcome}"
                _counts[key] = _counts.get(key, 0) + 1
                _duration[name] = _duration.get(name, 0) + elapsed
            logger.info(
                json.dumps({"operation": name, "outcome": outcome, "seconds": round(elapsed, 5)})
            )


def snapshot() -> dict:
    with _lock:
        return {
            "counts": dict(_counts),
            "total_seconds": dict(_duration),
            "scope": "this API/worker process only; content logging disabled",
        }
