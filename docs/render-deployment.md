# Deploy the full single-owner app on Render

This deploys the actual React console, FastAPI API, durable worker and PostgreSQL database. It is not the static sample. The root `render.yaml` uses one free web service running the API and worker together, plus free PostgreSQL. This is a hobby-project deployment with idle sleep and a database expiry, not permanent hosting. The optional `deploy/render-paid.example.yaml` is reference only and is not authorized for deployment.

## Prepare

1. In your local checkout, run `uv run python -m ffv2.auth`. Choose a strong workspace password when prompted; copy the generated hash directly into Render's secret settings. Do not put either value in Git or chat. The plaintext password is what you use on the login page.
2. In Render, create a Blueprint from this repository's `main` branch and review `render.yaml`. For a fresh account it declares one free web service and one free PostgreSQL database in Oregon. For the current account, reuse the existing `failure-forensics-project-db` instead of creating another database: create the web service directly and configure its internal database URL in the Dashboard. The Dashboard is the configuration source of truth for this manually created service; do not apply a parallel Blueprint to it.
3. Supply `FF_OWNER_PASSWORD_HASH` and `FF_GROQ_API_KEY` in Render's secure inputs. Both processes receive the same runtime environment. The key is never sent to the browser.
4. The start command `python -m ffv2.hosted project` runs Alembic under a PostgreSQL advisory lock, then supervises the API and worker. If either process exits, both stop so Render can restart the service. Services use Render's internal database URL with the psycopg driver normalized by Settings. There is no external database IP allowlist entry.
5. Open the web service's actual `onrender.com` URL. Its HTTPS origin is inferred from `RENDER_EXTERNAL_HOSTNAME`. For a custom domain, set `FF_PUBLIC_ORIGIN` to its exact HTTPS origin without a trailing slash, then redeploy.
6. Sign in, submit only the invented invoice first, inspect all outputs, review, replay and verify persistence after a restart. Do not announce a live service until these checks pass on Render.

Auto-deploys are disabled so web/worker/schema changes can be released deliberately. Deploy the combined service from the tested commit; no paid pre-deploy hook or separate worker is needed. The worker has no public HTTP endpoint. Only the owner should know the workspace password; this is not a multi-tenant SaaS and visitors must not share your workspace.

## Limits and failure behavior

- Sessions are opaque, stored hashed in PostgreSQL, expire after one hour and are revoked on logout. Changing the password hash invalidates existing sessions. Browser writes require the exact configured Origin. Spoofed proxy identity headers do not bypass hosted login.
- Login attempts share a database-backed limit of 10 per five minutes. All application mutations share `FF_MUTATIONS_PER_MINUTE` (default 30) across API instances.
- All worker Groq producer, judge and retry calls reserve from `FF_GROQ_DAILY_CALLS` (default 100 per UTC day). Failed calls consume a reservation. `FF_GROQ_MAX_COMPLETION_TOKENS` defaults to 4096 per call. These are request/output bounds, **not a currency spending guarantee**; configure Groq account spending controls too. Other applications using the same key are not governed by this database.
- A Linux parser child is limited to `FF_PARSER_MEMORY_MB` (default 256), eight CPU seconds and a ten-second wall deadline. Each API process runs at most one parser at once. API/worker memory is bounded by the chosen Render instance. Windows retains process/time/size isolation but cannot claim Linux RLIMIT enforcement.
- A database/control failure denies protected access or AI work rather than bypassing limits. An exhausted budget records `budget_exceeded`; an unavailable judge remains inconclusive.

## Backups, monitoring and rollback

The free database expires on **25 November 2026** and has no managed backups. Download important investigations from the run page before expiry; these JSON exports include the run and review history but are not a full database backup or an automatic restore format. Keep the local app for long-term use. A lasting hosted deployment requires a separately selected persistent database provider before expiry; no paid upgrade is authorized. Restore into a **new** database, compare data and run the app against that new database before relying on a backup. The CI restore drill uses actual pg_dump/pg_restore and compares every canonical table, but cannot certify a specific Render backup.

Use `/health/ready` for Render health checks (database/schema only, not provider accuracy), and monitor worker exits/restarts, queue delays, HTTP failures and Groq usage in the service/account dashboards. Configure Render account alert recipients yourself; no emails or external monitoring accounts were created.

Before releases: save a backup, record the tested Git commit, and keep the previous container revision. These migrations add tables only. Reverting code must retain the newer tables and use a prior image compatible with hosted mode and the current schema. Pre-hosted releases are not compatible rollback targets. Never run destructive downgrades; restore a verified backup to a new database if a schema-incompatible rollback becomes necessary. Test this against the intended Render environment before calling operations validated.

## External checks still required

Owner secret configuration, HTTPS login and a real hosted Groq producer run were verified on 26 October. Exact export comparison after restart remains unverified: readiness requests timed out on 28 October. Target-host database restore and alert-delivery checks remain outstanding. The legacy OIDC proxy mode is optional and remains separate from the built-in hosted owner login. Independent human evaluation and model-accuracy studies are not replaced by these engineering checks.

References: [Blueprint specification](https://render.com/docs/blueprint-spec), [compute plans](https://render.com/docs/compute-plans), [free-tier limits](https://render.com/docs/free).

## Free hosting constraints

The web service sleeps after 15 minutes without incoming traffic; opening it wakes it, which can take about a minute. Its worker also stops while asleep. Keep the page open while a run processes. PostgreSQL retains queued jobs across service restarts until database expiry. Do not store important files in the web container: its disk is temporary. Free hours are shared with other services in the workspace; existing RELAY configuration is untouched. Check account usage and spend limits, because a free compute plan is not an account-wide guarantee against usage charges.
