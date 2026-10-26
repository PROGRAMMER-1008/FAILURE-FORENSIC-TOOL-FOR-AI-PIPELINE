# Deploy the full single-owner app on Render

This deploys the actual React console, FastAPI API, durable worker and PostgreSQL database. It is not the static sample. The root `render.yaml` uses paid persistent compute; **do not apply it until you approve the price shown in your Render workspace**. No services were provisioned by committing the configuration.

## Prepare

1. In your local checkout, run `uv run python -m ffv2.auth`. Choose a strong workspace password when prompted; copy the generated hash directly into Render's secret settings. Do not put either value in Git or chat. The plaintext password is what you use on the login page.
2. In Render, create a Blueprint from this repository's `main` branch and review `render.yaml`. It declares one web service, one background worker and a private PostgreSQL database in the same region. Review the current price and storage before approving creation.
3. Supply `FF_OWNER_PASSWORD_HASH` and `FF_GROQ_API_KEY` in Render's secure inputs. The worker references the web service's Groq key. The key is never sent to the browser.
4. Render's web pre-deploy action runs Alembic once. The worker waits for revision 0003 before processing. Services use Render's internal database URL with the psycopg driver normalized by Settings. There is no external database IP allowlist entry.
5. Open the web service's actual `onrender.com` URL. Its HTTPS origin is inferred from `RENDER_EXTERNAL_HOSTNAME`. For a custom domain, set `FF_PUBLIC_ORIGIN` to its exact HTTPS origin without a trailing slash, then redeploy.
6. Sign in, submit only the invented invoice first, inspect all outputs, review, replay and verify persistence after a restart. Do not announce a live service until these checks pass on Render.

Auto-deploys are disabled so web/worker/schema changes can be released deliberately. Deploy the web migration and then the worker from the same tested commit. The worker has no public HTTP endpoint. Only the owner should know the workspace password; this is not a multi-tenant SaaS and visitors must not share your workspace.

## Limits and failure behavior

- Sessions are opaque, stored hashed in PostgreSQL, expire after one hour and are revoked on logout. Changing the password hash invalidates existing sessions. Browser writes require the exact configured Origin. Spoofed proxy identity headers do not bypass hosted login.
- Login attempts share a database-backed limit of 10 per five minutes. All application mutations share `FF_MUTATIONS_PER_MINUTE` (default 30) across API instances.
- All worker Groq producer, judge and retry calls reserve from `FF_GROQ_DAILY_CALLS` (default 100 per UTC day). Failed calls consume a reservation. `FF_GROQ_MAX_COMPLETION_TOKENS` defaults to 4096 per call. These are request/output bounds, **not a currency spending guarantee**; configure Groq account spending controls too. Other applications using the same key are not governed by this database.
- A Linux parser child is limited to `FF_PARSER_MEMORY_MB` (default 256), eight CPU seconds and a ten-second wall deadline. Each API process runs at most one parser at once. API/worker memory is bounded by the chosen Render instance. Windows retains process/time/size isolation but cannot claim Linux RLIMIT enforcement.
- A database/control failure denies protected access or AI work rather than bypassing limits. An exhausted budget records `budget_exceeded`; an unavailable judge remains inconclusive.

## Backups, monitoring and rollback

Enable and verify the paid database's backup retention in Render. Restore into a **new** database, compare data and run the app against that new database before relying on a backup. The CI restore drill uses actual pg_dump/pg_restore and compares every canonical table, but cannot certify a specific Render backup.

Use `/health/ready` for Render health checks (database/schema only, not provider accuracy), and monitor worker exits/restarts, queue delays, HTTP failures and Groq usage in the service/account dashboards. Configure Render account alert recipients yourself; no emails or external monitoring accounts were created.

Before releases: save a backup, record the tested Git commit, and keep the previous container revision. These migrations add tables only. Reverting code must retain the newer tables and use a prior image compatible with hosted mode and the current schema. Pre-hosted releases are not compatible rollback targets. Never run destructive downgrades; restore a verified backup to a new database if a schema-incompatible rollback becomes necessary. Test this against the intended Render environment before calling operations validated.

## External checks still required

Render account connection and approved billing; secret entry by the owner; real domain/TLS and service restart/restore checks; a live hosted Groq smoke. The legacy OIDC proxy mode is optional and remains separate from the built-in hosted owner login. Independent human evaluation and model-accuracy studies are not replaced by these engineering checks.

References: [Blueprint specification](https://render.com/docs/blueprint-spec), [compute plans](https://render.com/docs/compute-plans), [free-tier limits](https://render.com/docs/free).
