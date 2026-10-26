# Configuration

Direct V2 services read process variables prefixed `FF_` and do not implicitly load `.env`. The explicit local launcher (`start-local.cmd` or `.venv/Scripts/python -m ffv2.local`) loads the root `.env` and passes one shared configuration to migrations, API and worker. Process variables override file values. Restart after edits. `.env.example` contains blank-key synthetic defaults. Do not overwrite an existing `.env`. Never use `VITE_*` for secrets.

| Variable | Default / meaning |
| --- | --- |
| FF_DATABASE_URL | sqlite:///data/v2.db; PostgreSQL URL for reference deployment. Treat credentials as secret. |
| FF_MODE | local; demo is server-enforced read-only; private requires proxy configuration below. |
| FF_PROVIDER | fake for synthetic mechanics; ollama for local inference; groq for cloud inference. |
| FF_GROQ_API_KEY | Blank by default; backend-only credential. Missing keys block Groq submissions. |
| FF_PRODUCER_MODEL | llama3.1:8b; actual installed model identifier. |
| FF_JUDGE_MODEL | llama3.1:8b; separate configurable evaluator model. |
| FF_OLLAMA_URL | http://127.0.0.1:11434; operator-controlled, never accepted from a request. |
| FF_DEADLINE_SECONDS | 45 per call, maximum 120. |
| FF_MAX_CHARACTERS | 20000; context budgets reject oversized requests without truncation. |
| FF_MAX_UPLOAD_BYTES | 2000000; enforced while receiving, including chunked bodies. |
| FF_LEASE_SECONDS | 180, minimum 150; keep above each call deadline with margin. |
| FF_MAX_JOB_ATTEMPTS | 3 recovery claims; per-step transient retry budget is 2. |
| FF_TRUSTED_PROXY_IPS | JSON list of exact proxy peer IPs; empty by default. Private mode requires it. |
| FF_AUTHORIZED_SUBJECT | One exact user value forwarded by the authenticating proxy; empty by default. |
| FF_TEST_DATABASE_URL | Test runner only; disposable PostgreSQL database. |
| FF_BROWSER_URL | Playwright only; defaults to http://127.0.0.1:8000. |

No variable values are returned from secret-bearing configuration. The status endpoint reports provider/model choices and mode. Errors are sanitized. Private settings hide validation inputs in exception messages.

Docker-to-host Ollama: Windows Docker Desktop typically uses host.docker.internal. Linux requires a deliberate host-gateway mapping. Keep Ollama on a private interface and never publish its port. API and worker must share provider settings.

The local template sets producer/judge to `openai/gpt-oss-20b` and database to `data/local-ai.db`; these override the code defaults listed above. The launcher opens port 8001, requires local mode, and will not start a worker if Groq lacks a key. The UI returns only a credential-presence status, never the key. Same-model evaluation remains correlated. The optional interactive `scripts/start_groq.py` launcher still works without a dotenv file.
