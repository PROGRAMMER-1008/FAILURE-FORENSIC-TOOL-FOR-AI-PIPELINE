import asyncio
import json
from datetime import datetime
from pathlib import Path
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import Field, ValidationError
from sqlalchemy import select

from ffv2.db import cases, datasets, engine, reviews, experiments as experiments_table, results
from ffv2.experiments import ExperimentRequest, experiment, compare
from ffv2.datasets import FreezeRequest, freeze
from ffv2.models import Model, ReviewInput, Run, uid
from ffv2.privacy import fingerprint, redact
from ffv2.replay import ReplayRequest, replay
from ffv2.limits import reserve
from ffv2.auth import gate
from ffv2.db import usage_windows, owner_sessions
from ffv2.settings import Settings
from ffv2.store import Conflict, Missing, Store
from ffv2.uploads import DocumentError, isolated_extract
from ffv2.worker import SYNTHETIC_SOURCE
from ffv2.observability import operation, snapshot


class Submit(Model):
    text: str = Field(min_length=1, max_length=20000)
    idempotency_key: str = Field(min_length=1, max_length=100)
    injected: bool = False


class BodyLimit:
    def __init__(self, app, maximum):
        self.app, self.maximum = app, maximum

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        # Buffer only up to the hard cap before any parser sees bytes.
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > self.maximum:
                response = JSONResponse({"error": "request_too_large"}, 413)
                return await response(scope, receive, send)
            if not message.get("more_body"):
                break
        sent = False

        async def bounded_receive():
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, bounded_receive, send)


def create_app(settings: Settings | None = None, store: Store | None = None) -> FastAPI:
    settings = settings or Settings()
    store = store or Store(engine(settings.database_url))
    code_fingerprint = fingerprint(
        {
            name: Path(__file__).with_name(name).read_text(encoding="utf-8")
            for name in ("models.py", "providers.py", "diagnosis.py", "worker.py")
        }
    )
    app = FastAPI(title="Failure Forensics", version="2.0.0")
    parser_slot = asyncio.Semaphore(1)
    app.add_middleware(BodyLimit, maximum=settings.max_upload_bytes)

    @app.middleware("http")
    async def boundary(request: Request, call_next):
        request_id = uid()
        peer_key = request.client.host if request.client else "unknown"
        if settings.mode == "hosted":
            try:
                auth_response = await gate(request, settings, store.engine)
            except Exception:
                return JSONResponse({"error": "authentication_unavailable"}, 503)
            if auth_response is not None:
                return auth_response
        if settings.mode == "private" and request.url.path != "/health/live":
            peer = request.client.host if request.client else ""
            if peer not in settings.trusted_proxy_ips:
                return JSONResponse({"error": "Trusted authentication proxy required"}, 401)
            if request.headers.get("x-auth-request-user") != settings.authorized_subject:
                return JSONResponse({"error": "Identity not authorized for this workspace"}, 403)
        if settings.mode == "demo" and request.method not in {"GET", "HEAD", "OPTIONS"}:
            return JSONResponse(
                {"error": "Recorded demo is read-only", "request_id": request_id}, 403
            )
        if settings.mode == "local":
            host = request.headers.get("host", "").split(":")[0]
            origin = request.headers.get("origin")
            if host not in {"127.0.0.1", "localhost", "testserver", "api"}:
                return JSONResponse({"error": "Untrusted host"}, 403)
            if origin and origin != f"{request.url.scheme}://{request.headers.get('host')}":
                return JSONResponse({"error": "Cross-origin request denied"}, 403)
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            scope = "owner" if settings.mode in {"private", "hosted"} else fingerprint(peer_key)
            try:
                allowed = await asyncio.to_thread(
                    reserve,
                    store.engine,
                    "mutation-" + scope,
                    settings.mutations_per_minute,
                    60,
                )
            except Exception:
                return JSONResponse({"error": "usage_controls_unavailable"}, 503)
            if not allowed:
                return JSONResponse(
                    {"error": "mutation_rate_limit", "request_id": request_id},
                    429,
                    headers={"Retry-After": "60"},
                )
        try:
            with operation("http_request"):
                response = await call_next(request)
        except Exception:
            response = JSONResponse({"error": "internal_error", "request_id": request_id}, 500)
        response.headers.update(
            {
                "X-Request-ID": request_id,
                "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "no-referrer",
                "Cache-Control": "no-store",
                "Content-Security-Policy": "default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'",
            }
        )
        return response

    @app.exception_handler(Missing)
    async def missing(request, exc):
        return JSONResponse({"error": "not_found"}, 404)

    @app.exception_handler(Conflict)
    async def conflict(request, exc):
        return JSONResponse({"error": str(exc)}, 409)

    @app.exception_handler(RequestValidationError)
    @app.exception_handler(ValidationError)
    async def invalid(request, exc):
        return JSONResponse({"error": "invalid_request"}, 422)

    @app.get("/health/live")
    def live():
        return {"status": "alive"}

    @app.get("/health/ready")
    def ready():
        try:
            with store.engine.connect() as conn:
                conn.execute(select(cases.c.id).limit(1))
                conn.execute(select(usage_windows.c.key).limit(1))
                conn.execute(select(owner_sessions.c.id).limit(1))
            return {
                "database": "ready",
                "provider": "not_checked" if settings.provider != "fake" else "synthetic",
            }
        except Exception:
            raise HTTPException(503, "Database schema unavailable") from None

    @app.get("/api/v1/config")
    def config():
        return {
            "mode": settings.mode,
            "provider": settings.provider,
            "ai_ready": settings.ai_ready,
            "credential_status": "present_not_verified"
            if settings.provider == "groq" and settings.ai_ready
            else ("missing" if settings.provider == "groq" else "not_required"),
            "producer_model": settings.producer_model
            if settings.provider != "fake"
            else "synthetic-1",
            "judge_model": settings.judge_model
            if settings.provider != "fake"
            else "injected-fixture-1",
            "correlated_judge": settings.producer_model == settings.judge_model,
            "groq_daily_calls": settings.groq_daily_calls,
            "groq_max_completion_tokens": settings.groq_max_completion_tokens,
            "max_characters": settings.max_characters,
            "max_upload_bytes": settings.max_upload_bytes,
            "retention": (
                "Hosted database retention depends on your hosting plan; export before expiry"
                if settings.mode == "hosted"
                else "Local until explicit deletion; secret redaction is not comprehensive PII detection"
            ),
            "sample": SYNTHETIC_SOURCE,
        }

    def submit(body: Submit):
        if not settings.ai_ready:
            raise HTTPException(
                503,
                "Groq key missing. Set FF_GROQ_API_KEY in hosting settings and redeploy."
                if settings.mode == "hosted"
                else "Groq key missing. Add FF_GROQ_API_KEY to .env and restart.",
            )
        if len(body.text) > settings.max_characters:
            raise HTTPException(413, "Character limit exceeded")
        if body.injected and (settings.provider != "fake" or body.text != SYNTHETIC_SOURCE):
            raise HTTPException(422, "Injection requires the synthetic sample and fake provider")
        run = store.enqueue(
            Run(
                source=redact(body.text),
                source_hash=fingerprint(body.text),
                config={
                    "provider": settings.provider,
                    "code_fingerprint": code_fingerprint,
                    "prompt_version": "document-producer-1",
                    "judge_policy_version": "source-faithfulness-1",
                    "producer_model": settings.producer_model,
                    "judge_model": settings.judge_model,
                    "injected": body.injected,
                    "execution_mode": "synthetic" if settings.provider == "fake" else "live",
                },
            ),
            body.idempotency_key,
        )
        return {
            "id": run.id,
            "status": run.status,
            "status_url": f"/api/v1/runs/{run.id}",
            "events_url": f"/api/v1/runs/{run.id}/events",
        }

    @app.post("/api/v1/runs", status_code=202)
    def create_run(body: Submit):
        return submit(body)

    @app.post("/api/v1/uploads", status_code=202)
    async def upload(request: Request):
        if not settings.ai_ready:
            raise HTTPException(503, "Groq key missing. Add FF_GROQ_API_KEY to .env and restart.")
        # Raw upload, not multipart: bounded middleware covers chunked bodies too.
        data = await request.body()
        try:
            await asyncio.wait_for(parser_slot.acquire(), timeout=2)
        except TimeoutError:
            raise HTTPException(429, "Document parser is busy; retry shortly") from None
        try:
            source = await asyncio.to_thread(
                isolated_extract,
                data,
                request.headers.get("content-type", ""),
                settings.max_characters,
                settings.parser_memory_mb,
            )
        except DocumentError as exc:
            raise HTTPException(422, str(exc)) from None
        finally:
            parser_slot.release()
        return submit(
            Submit(text=source, idempotency_key=request.headers.get("idempotency-key", ""))
        )

    @app.get("/api/v1/runs")
    def list_runs(
        limit: int = Query(25, ge=1, le=100),
        offset: int = Query(0, ge=0),
        status: str | None = None,
        q: str = Query("", max_length=100),
        since: datetime | None = None,
        oldest_first: bool = False,
    ):
        return {
            "items": store.list_runs(
                limit, offset, status, q, since.isoformat() if since else None, oldest_first
            ),
            "limit": limit,
            "offset": offset,
        }

    @app.get("/api/v1/stats")
    def stats():
        return store.stats()

    @app.get("/api/v1/metrics")
    def metrics():
        return snapshot()

    @app.get("/api/v1/runs/{run_id}")
    def detail(run_id: UUID):
        return store.get(str(run_id))

    @app.get("/api/v1/runs/{run_id}/export")
    def export_run(run_id: UUID):
        assert store is not None
        return JSONResponse(
            {
                "format": "failure-forensics-investigation-1",
                "run": store.get(str(run_id)).model_dump(mode="json"),
                "reviews": history(run_id),
            },
            headers={"Content-Disposition": f'attachment; filename="investigation-{run_id}.json"'},
        )

    @app.post("/api/v1/runs/{run_id}/cancel", status_code=202)
    def cancel(run_id: UUID):
        store.cancel(str(run_id))
        return {"status": "Cancellation requested; an in-flight call may finish"}

    @app.get("/api/v1/runs/{run_id}/events")
    async def stream(run_id: UUID, request: Request):
        store.get(str(run_id))
        try:
            cursor = max(0, int(request.headers.get("last-event-id", "0")))
        except ValueError:
            raise HTTPException(422, "Invalid event cursor") from None

        async def generate():
            nonlocal cursor
            while True:
                batch = await asyncio.to_thread(store.event_list, str(run_id), cursor)
                for item in batch:
                    cursor = item["sequence"]
                    item["recorded_demo"] = settings.mode == "demo"
                    yield f"id: {cursor}\nevent: {item['kind']}\ndata: {json.dumps(item)}\n\n"
                run = await asyncio.to_thread(store.get, str(run_id))
                if run.status in {"succeeded", "failed", "cancelled"} and len(batch) < 200:
                    return
                if await request.is_disconnected():
                    return
                yield ": heartbeat\n\n"
                await asyncio.sleep(1)

        return StreamingResponse(
            generate(), media_type="text/event-stream", headers={"X-Accel-Buffering": "no"}
        )

    @app.post("/api/v1/runs/{run_id}/reviews")
    def review(run_id: UUID, body: ReviewInput):
        return store.review(str(run_id), body)

    @app.get("/api/v1/runs/{run_id}/reviews")
    def history(run_id: UUID):
        store.get(str(run_id))
        with store.engine.connect() as conn:
            return list(
                conn.execute(
                    select(reviews.c.payload)
                    .where(reviews.c.run_id == str(run_id))
                    .order_by(reviews.c.revision)
                ).scalars()
            )

    @app.post("/api/v1/runs/{run_id}/replays", status_code=202)
    def replay_run(run_id: UUID, body: ReplayRequest):
        original = store.get(str(run_id))
        if (
            body.mode == "reexecute"
            and original.config.get("provider") == "groq"
            and not settings.groq_api_key.get_secret_value().strip()
        ):
            raise HTTPException(503, "Groq key missing. Add FF_GROQ_API_KEY to .env and restart.")
        result = replay(store, original, body)
        return {"id": result.id, "mode": body.mode}

    @app.get("/api/v1/datasets")
    def dataset(limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0)):
        with store.engine.connect() as conn:
            return [
                dict(row)
                for row in conn.execute(
                    select(cases)
                    .where(cases.c.payload["label_state"].as_string() == "reviewed")
                    .order_by(cases.c.id)
                    .limit(limit)
                    .offset(offset)
                ).mappings()
            ]

    @app.get("/api/v1/experiments")
    def experiments():
        with store.engine.connect() as conn:
            return list(
                conn.execute(
                    select(experiments_table.c.payload)
                    .order_by(experiments_table.c.created_at.desc())
                    .limit(25)
                ).scalars()
            )

    @app.post("/api/v1/experiments", status_code=201)
    def create_experiment(body: ExperimentRequest):
        return experiment(store, body)

    @app.get("/api/v1/experiments/{experiment_id}/results")
    def experiment_results(
        experiment_id: str, limit: int = Query(100, ge=1, le=250), offset: int = Query(0, ge=0)
    ):
        with store.engine.connect() as conn:
            if (
                conn.scalar(
                    select(experiments_table.c.id).where(experiments_table.c.id == experiment_id)
                )
                is None
            ):
                raise Missing()
            return list(
                conn.execute(
                    select(results.c.payload)
                    .where(results.c.experiment_id == experiment_id)
                    .order_by(results.c.id)
                    .limit(limit)
                    .offset(offset)
                ).scalars()
            )

    @app.get("/api/v1/runs/{run_id}/comparison")
    def comparison(run_id: UUID):
        return compare(store, store.get(str(run_id)))

    @app.post("/api/v1/datasets/versions", status_code=201)
    def freeze_dataset(body: FreezeRequest):
        return freeze(store, body)

    @app.get("/api/v1/datasets/versions")
    def dataset_versions():
        with store.engine.connect() as conn:
            return list(
                conn.execute(
                    select(datasets.c.payload).order_by(datasets.c.created_at.desc()).limit(100)
                ).scalars()
            )

    @app.get("/api/v1/datasets/versions/{version}/export")
    def export_dataset(version: str):
        if len(version) != 64 or any(c not in "0123456789abcdef" for c in version):
            raise HTTPException(422, "Invalid dataset version")
        with store.engine.connect() as conn:
            result = conn.scalar(select(datasets.c.payload).where(datasets.c.id == version))
        if result is None:
            raise Missing()
        return redact(result)

    frontend = Path("frontend/dist")
    if frontend.is_dir():
        app.mount("/assets", StaticFiles(directory=frontend / "assets"), name="assets")

        @app.get("/")
        def home():
            return FileResponse(frontend / "index.html")

    return app


app = create_app()
