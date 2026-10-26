# API contracts

The running API exposes OpenAPI at `/openapi.json` and interactive docs at `/docs`.
API version prefix: `/api/v1`. Application errors use sanitized JSON with no raw provider exception or request content. Response X-Request-ID supports correlation. Pydantic validates bodies/UUID paths; missing records return 404 and revision/idempotency conflicts 409.

| Method/path | Contract |
| --- | --- |
| POST /runs | text, idempotency_key, injected=false; 202 with run/status/events URLs. |
| POST /uploads | Raw TXT/PDF/DOCX bytes, Content-Type and Idempotency-Key headers; no client path accepted. |
| GET /runs | limit 1–100, offset >=0, status filter; metadata-only list. |
| GET /runs/{UUID} | Full sanitized source, attempts, judgments, finding and revision. |
| GET /runs/{UUID}/events | SSE ordered IDs, Last-Event-ID replay, heartbeats and terminal close. Demo events explicitly marked recorded_demo. |
| POST /runs/{UUID}/cancel | Cooperative cancellation; in-flight calls may complete. |
| POST /runs/{UUID}/reviews | reviewer, revision, target_finding_revision, verdict, origins, optional category/notes/expected_output, idempotency_key. |
| GET /runs/{UUID}/reviews | Append-only history. |
| POST /runs/{UUID}/replays | recorded/reexecute mode, description, key; optional step_id/corrected_output pair. |
| GET /runs/{UUID}/comparison | Before/after structured outputs, changes and optional exact-field score. |
| GET /datasets | Paginated eligible feedback cases. |
| POST /datasets/versions | name and unique case_ids; immutable content-addressed feedback snapshot. |
| GET /datasets/versions | Historical snapshots. |
| GET /datasets/versions/{hash}/export | Sanitized snapshot JSON. |
| POST /experiments | mode=synthetic, dataset_version=curated-mechanics-1, idempotency_key. No live model calls. |
| GET /experiments | Generated synthetic report history. |
| GET /experiments/{hash}/results | Paginated case-level results. |
| GET /config, /stats, /metrics | Safe status, SQL aggregates, content-free operational counters. |

Example expected output for replay scoring: `{"summarize":{"summary":"Synthetic invoice total: 814 EUR"}}`.
Only explicitly supplied fields are compared; absent gold output is unavailable, not a zero score.

Demo rejects mutations server-side. Private mode requires a trusted proxy peer and exactly one allowed subject for every data/config/export route. Liveness alone is public. Mutation rate limit is 30/minute per peer per API process; production proxy limits must supplement it.
