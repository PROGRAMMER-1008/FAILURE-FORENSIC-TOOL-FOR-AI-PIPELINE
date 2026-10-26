# Operations runbook

- API alive but not ready: verify DB connectivity and `uv run python -m alembic upgrade head`; do not print the database URL.
- Queued jobs: verify worker is running with the same DB/provider settings. Inspect event IDs. Never mark a run successful manually to clear the queue.
- Worker crash: wait for lease expiry (180s default); a new claim fences the previous generation. Calls may repeat. Completed attempts stay persisted. Recovery claims stop at the configured budget.
- Cancellation: stops future work; an in-flight call may finish before terminal cancellation is recorded.
- Judge unavailable: retain outputs, show inconclusive quality. Check judge model installation and budget without changing pipeline execution status.
- Parser failures: use supported UTF-8 text/PDF/DOCX; OCR/encrypted PDF unsupported. Keep document contents out of logs/issues.

SQLite backup/restore (stop writers for a coordinated release snapshot):

```powershell
uv run python -m ffv2.operations backup-sqlite data/v2.db backups/pre-release.db
uv run python -m ffv2.operations backup-sqlite backups/pre-release.db data/restored.db
```

The backup API verifies SQLite integrity; tests restore disposable data and check persisted state. Destination must not already exist. Point a test API at restored.db before switching the real deployment. PostgreSQL tooling below uses pg_dump/pg_restore into a new database; the real PostgreSQL restore/comparison drill passed in GitHub CI on 26 October 2026. Repeat the drill against the intended host before relying on its backups.

Docker PostgreSQL tooling is provided and exercised in CI; local Docker is still unavailable:

```powershell
uv run python -m scripts.postgres_backup backup --container YOUR_PRIVATE_DB_CONTAINER --database forensics --user forensics --file backups/postgres.dump
uv run python -m scripts.postgres_backup restore-new --container YOUR_PRIVATE_DB_CONTAINER --database forensics_restore_check --user forensics --file backups/postgres.dump
```

Restore refuses an existing database and performs a table query, but operator comparison and app smoke tests are still required. Do not put passwords on command lines. Existing container authentication is used normally; dump contents and errors are not printed.

Observe `/health/live`, `/health/ready`, `/api/v1/stats` and `/api/v1/metrics`. Operational counters are per-process, low-cardinality and content-free; production aggregation/alerts and queue-age histograms remain incomplete. Suggested alerts: sustained readiness failure; queued work without a worker; repeated provider timeouts; expired leases; disk/DB capacity. Investigate the dependency or worker rather than retrying indefinitely.

Retention target must be chosen by the owner. Backups and downloaded exports are not magically erased by deleting a run. No RPO/RTO promise is made.


Hosted owner access: use `/auth/login`; `/auth/logout` revokes the stored session. Password-hash rotation revokes all earlier sessions. A login throttle lasts up to five minutes. Changing the origin requires an exact HTTPS origin in FF_PUBLIC_ORIGIN and a service restart. Do not bypass sign-in to diagnose a hosted outage.

Groq daily allowance exhaustion: attempts record budget_exceeded, and no further quota-protected call is sent. The window resets at UTC midnight. Do not delete usage_windows to evade the limit; review the actual account budget before deliberately raising FF_GROQ_DAILY_CALLS. Provider errors and unavailable judges remain truthful failure/inconclusive states.
