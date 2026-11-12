# Failure Forensics

An AI pipeline investigation console for tracing document evidence through extraction, classification and summarization. The free-hosted public demo is available now; shared fair-use limits and temporary database hosting make it a project demo, not a production SaaS.

The v2 application lives in `ffv2/` and `frontend/`. Original pipeline modules remain available for compatibility and the legacy analyzer baseline. Original README: [legacy notes](docs/legacy-readme.md). Detailed acceptance gaps: [implementation status](docs/implementation-status.md).

## Try the public application

Open the **[public Failure Forensics app](https://failure-forensics-pk.vercel.app)**. Visitors do not need an account, password or personal Groq key. Vercel serves the React frontend and proxies API requests to the FastAPI service on Render; Groq credentials stay on the server. Use the invented invoice or other non-sensitive content. Public visitor workspaces are isolated and subject to shared fair-use limits. The free Render database is temporary and expires on **25 November 2026**.

## Watch the public AI walkthrough

[![Watch the public Failure Forensics walkthrough](launch/public-demo-cover.png)](https://github.com/PROGRAMMER-1008/FAILURE-FORENSIC-TOOL-FOR-AI-PIPELINE/blob/main/launch/failure-forensics-public-demo.mp4)

[Watch or download the 43-second public demo](https://github.com/PROGRAMMER-1008/FAILURE-FORENSIC-TOOL-FOR-AI-PIPELINE/raw/refs/heads/main/launch/failure-forensics-public-demo.mp4). The walkthrough uses an invented invoice in the live Groq-backed app. All three generation steps completed, but the evaluator returned invalid citation offsets, so Failure Forensics kept the diagnosis inconclusive instead of presenting an unsupported cause. This is one observed run, not a model-accuracy benchmark.

[View deployment details and limits](docs/public-deployment.md) or [read the public quickstart](docs/hosted-quickstart.md). The older owner-only Render URL is not the public application.

The full application can also run locally with Groq or Ollama, and a private single-owner Render configuration remains available through the [Render guide](docs/render-deployment.md). See the [deployment readiness record](docs/deployment-readiness.md) for the exact hosting checks and limitations.

## Easy local setup (Windows)

For a fresh clone, install Git, [uv](https://docs.astral.sh/uv/getting-started/installation/) and Node.js 22.22.2. Then run from PowerShell:

```powershell
git clone https://github.com/PROGRAMMER-1008/FAILURE-FORENSIC-TOOL-FOR-AI-PIPELINE.git
cd FAILURE-FORENSIC-TOOL-FOR-AI-PIPELINE
uv sync --frozen
npm --prefix frontend ci
npm --prefix frontend run build
if (!(Test-Path .env)) { Copy-Item .env.example .env }
.\start-local.cmd
```

After first-time setup, double-click `start-local.cmd`. It loads your local configuration, migrates the selected database, and starts the API and worker. Open http://127.0.0.1:8001. Keep the terminal open; Ctrl+C stops the services. The default fake provider lets you explore without a key. Do not overwrite an existing `.env`.

When ready for real AI, edit `.env` locally:

```dotenv
FF_PROVIDER=groq
FF_GROQ_API_KEY=your-key-goes-here
```

Keep the configured producer/judge model identifiers or choose models available to your Groq account. Save and restart the launcher. Settings & status shows whether the key is present; presence does not mean authentication was verified. Missing-key mode allows browsing but blocks new AI work. Submitted content goes to Groq and uses your quota. Never send the key in chat or commit `.env`.

The launcher uses `data/local-ai.db` with the supplied template. The older synthetic and Groq preview databases remain intact. Process environment variables override file values. Direct API/worker commands below remain environment-only; use the launcher when you want `.env` support.

## Run locally without a GPU or API key

Prerequisites: uv, Python 3.12.10 (uv can install it), Node 22.22.2. Do not execute the old `forensic/` environment.

```powershell
uv sync --frozen
npm --prefix frontend ci
npm --prefix frontend run build
uv run python -m alembic upgrade head
uv run python -m uvicorn ffv2.api:app --host 127.0.0.1 --port 8000 --no-access-log
```

In a second terminal, from the repository root:

```powershell
uv run python -m ffv2.worker
```

Open [the local console](http://127.0.0.1:8000), choose **New investigation → Load invented invoice → Queue investigation**. The default fake provider deliberately supports synthetic mechanics, not arbitrary-document understanding. The sample's extraction can inject `999 EUR` while the source says `814 EUR`. Diagnosis identifies extraction as a suspected origin and summarization as an observed propagated symptom.

Review the diagnosis, optionally provide gold output, then re-execute with corrected extraction. The original remains intact; only affected descendants are rerun. No real-model quality or causal improvement is implied by this injected demonstration.

## Local Ollama

Install/run Ollama separately and provision your chosen model yourself. No model downloads happen during tests/builds.

```powershell
$env:FF_PROVIDER='ollama'
$env:FF_PRODUCER_MODEL='your-installed-model'
$env:FF_JUDGE_MODEL='your-installed-judge-model'
```

Set the same configuration in API and worker terminals before starting them. Source content is sent to the configured local Ollama endpoint. Same-model judging can have correlated errors. There is no cloud fallback. Real Ollama execution was not validated in this implementation session.

## What is implemented

- Versioned tracing envelopes, actual dependency graph, strict schema errors, sanitized literal responses, partial-run checkpoints.
- Canonical SQLAlchemy relational persistence and explicit Alembic migration; local SQLite and PostgreSQL queue support.
- Durable claims, leases/fencing, bounded retry, real SSE events, cancellation and idempotent submissions.
- React console with source/attempt/evidence inspection, append-only human reviews and re-execution interventions.
- Bounded document uploads including DOCX tables, parser isolation/deadline, source-context rejection rather than silent truncation.
- Dry-run legacy import, stable IDs, immutable feedback dataset snapshots, synthetic benchmark, SQLite backup/restore and deletion tooling.
- Hosted owner sign-in and password-free visitor mode with isolated sessions, shared request budgets and Linux parser resource limits.
- Free Render combined web/worker and PostgreSQL Blueprint; read-only demo and optional trusted-proxy/OIDC boundaries.

## Verification

![Synthetic investigation console](docs/screenshots/investigation-wide.png)

Screenshots contain only the invented sample. A [narrow-layout capture](docs/screenshots/investigation-narrow.png) is also available.

```powershell
uv run pytest
uv run ruff check
uv run ruff format --check
uv run mypy
uv run python scripts/scan_secrets.py
uv run python -m ffv2.benchmark
npm --prefix frontend run lint
npm --prefix frontend test
npm --prefix frontend run build
```

Browser tests require a running synthetic API/worker and Playwright Chromium. Disable shared-cache cleanup before installing:

```powershell
$env:PLAYWRIGHT_SKIP_BROWSER_GC='1'
npm --prefix frontend exec -- playwright install chromium
npm --prefix frontend run e2e
```

PostgreSQL tests require `FF_TEST_DATABASE_URL` pointing to a **disposable** database. They skip with a reason otherwise. SQLite tests do not establish PostgreSQL concurrency behavior. The session also ran the PostgreSQL claim/fencing test separately and built/smoke-tested a local container.

See [configuration](docs/configuration.md), [architecture](docs/architecture.md), [migration](docs/migration.md), [deployment](docs/deployment.md), [runbook](docs/runbook.md), [security](docs/security.md), and [evaluation](docs/evaluation.md).

No services have been published or deployed. Direct service commands do not auto-load `.env`; the explicit local launcher reads it when you run it. Supply process variables deliberately; never put secrets in frontend variables. No license has been selected on the owner's behalf.

## Groq cloud API

From a PowerShell terminal in this repository, run:

```powershell
.\.venv\Scripts\python.exe scripts/start_groq.py
```

The launcher asks for a model (default `openai/gpt-oss-20b`) and then your API key in a hidden prompt. It never reads .env or saves the key to a file; child processes receive it in their environment. Open http://127.0.0.1:8001 and keep the terminal open. Ctrl+C stops both services. The separate database is data/groq-preview.db; the synthetic preview on port 8000 is unaffected.

Submitting a document sends redacted text and intermediate outputs to Groq. A successful three-step run normally makes six calls (three generation, three evaluation); bounded retries may add calls. Account quotas and charges apply. Same-model evaluation may have correlated errors. JSON object mode is locally validated against the pipeline contracts; valid JSON is not a guarantee of correct facts or schema compliance. HTTP authentication/rate-limit/provider failures are sanitized as provider_error; there is no fallback. Live Groq acceptance has not been run without a user-configured credential.

For manual startup, set FF_PROVIDER=groq, FF_GROQ_API_KEY, FF_PRODUCER_MODEL and FF_JUDGE_MODEL in both process environments. Never put the API key in frontend variables or source files. The model must be available to your Groq account.

API reference: https://console.groq.com/docs/api-reference
Model availability: https://console.groq.com/docs/models
